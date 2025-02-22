import os
import json
import logging
from typing import Optional, Dict, Any, List
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
import psycopg2

from drf_pydantic import BaseModel
from pydantic import Field

from core.logger import get_logger
from example.ai_client_new import AiBaseClient, OpenRouterConfig, OpenRouterModels

logger = get_logger(__name__, level=logging.INFO, log_to_file=True)

class CodeAnalysisResult(BaseModel):
    """Model for AI code analysis response."""
    project_type: str = Field(..., description="Type of the algotrading project")
    main_features: List[str] = Field(..., description="List of main features")
    technologies: List[str] = Field(..., description="List of key technologies used")
    risk_score: float = Field(..., ge=0, le=1, description="Risk assessment score (0-1)")
    analysis_summary: str = Field(..., description="Summary of the project analysis")

class AIAnalysisService:
    """Service for analyzing repository code using LLM."""

    def __init__(self, kafka_bootstrap_servers: str, db_config: Dict[str, Any]):
        self.consumer = KafkaConsumer(
            'repository.tasks',
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='ai-analysis-service'
        )
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        self.db_config = db_config

        # Initialize AI client
        config = OpenRouterConfig(
            model=OpenRouterModels.OPENAI_GPT_4O,
            verbose=True,
            fallback_to_free=True,
            order_preference=["anthropic", "openai", "google"]
        )
        self.ai_client = AiBaseClient(
            config=config,
            typed_response=CodeAnalysisResult
        )

    def update_repository_status(self, repo_url: str, status: str, error: Optional[str] = None):
        """Update repository status in database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute(
                """UPDATE repositories 
                   SET status = %s, 
                       last_updated = %s,
                       error = %s
                   WHERE url = %s""",
                (status, datetime.now(), error, repo_url)
            )
            
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Database error: {str(e)}")

    def analyze_repository(self, repo_path: str) -> Optional[CodeAnalysisResult]:
        """Analyze repository code using LLM."""
        try:
            # Prepare system prompt for code analysis
            system_prompt = """
            You are an expert code analyzer specializing in algotrading projects.
            Analyze the provided code and provide detailed insights about the project.
            Focus on identifying key features, technologies used, and potential risks.
            """

            # Prepare user prompt with repository information
            user_prompt = f"Analyze the algotrading project at {repo_path}. "
            user_prompt += "Provide a comprehensive analysis including project type, features, technologies, and risks."

            # Get AI analysis
            response = self.ai_client.get_response(
                prompt=user_prompt,
                system_prompt=system_prompt
            )

            return response

        except Exception as e:
            logger.error(f"Error analyzing repository: {str(e)}")
            return None

    def save_analysis_results(self, repo_url: str, analysis: CodeAnalysisResult):
        """Save analysis results to database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute(
                """UPDATE repositories 
                   SET analysis_data = %s,
                       risk_score = %s,
                       analyzed_at = %s
                   WHERE url = %s""",
                (json.dumps(analysis.dict()), analysis.risk_score, datetime.now(), repo_url)
            )
            
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving analysis results: {str(e)}")

    def run(self):
        """Main service loop."""
        logger.info("AI Analysis Service started. Waiting for messages...")
        try:
            for message in self.consumer:
                data = message.value
                repo_url = data.get('repo_url')
                repo_path = data.get('repo_path')
                task = data.get('task')

                if task == 'analyze' and repo_url and repo_path:
                    logger.info(f"Analyzing repository: {repo_url}")
                    
                    # Update status
                    self.update_repository_status(repo_url, 'ANALYZING')
                    
                    # Perform analysis
                    analysis = self.analyze_repository(repo_path)
                    
                    if analysis:
                        # Save results
                        self.save_analysis_results(repo_url, analysis)
                        self.update_repository_status(repo_url, 'ANALYZED')
                        
                        # Send status update
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'ANALYZED',
                            'analysis': analysis.dict()
                        })
                    else:
                        error_msg = "Analysis failed"
                        self.update_repository_status(repo_url, 'ANALYSIS_FAILED', error_msg)
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'ANALYSIS_FAILED',
                            'error': error_msg
                        })

        except KeyboardInterrupt:
            logger.info("Shutting down AI Analysis Service...")

if __name__ == "__main__":
    # Configuration
    kafka_config = {
        'bootstrap_servers': 'localhost:9092'
    }
    
    db_config = {
        'dbname': 'algotrading_monitor',
        'user': 'algotrading',
        'password': 'algotrading_pass',
        'host': 'localhost',
        'port': '5432'
    }
    
    # Start the service
    service = AIAnalysisService(kafka_config['bootstrap_servers'], db_config)
    service.run()