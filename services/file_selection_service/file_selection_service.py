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

class FileSelectionResult(BaseModel):
    """Model for file selection response."""
    selected_files: List[str] = Field(..., description="List of selected important files")
    selection_criteria: List[str] = Field(..., description="Criteria used for file selection")
    file_descriptions: Dict[str, str] = Field(..., description="Brief description of each selected file")

class FileSelectionService:
    """Service for selecting important files from repositories using LLM."""

    def __init__(self, kafka_bootstrap_servers: str, db_config: Dict[str, Any]):
        self.consumer = KafkaConsumer(
            'repository.tasks',
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='file-selection-service'
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
            typed_response=FileSelectionResult
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

    def select_files(self, repo_path: str) -> Optional[FileSelectionResult]:
        """Select important files from repository using LLM."""
        try:
            # Prepare system prompt for file selection
            system_prompt = """
            You are an expert in algorithmic trading systems and code analysis.
            Your task is to identify the most important files in a trading project repository
            that are crucial for understanding the trading logic, risk management,
            and overall system architecture.
            Focus on files containing:
            1. Trading strategies and algorithms
            2. Risk management logic
            3. Main configuration files
            4. Core system components
            5. API integrations with exchanges
            """

            # Get list of all files in repository
            all_files = []
            for root, _, files in os.walk(repo_path):
                for file in files:
                    if not file.startswith('.') and not 'node_modules' in root:
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        all_files.append(rel_path)

            # Prepare user prompt with repository information
            user_prompt = f"Analyze the following files in the repository and select the most important ones for algorithmic trading analysis:\n{json.dumps(all_files, indent=2)}"

            # Get AI analysis
            response = self.ai_client.get_response(
                prompt=user_prompt,
                system_prompt=system_prompt
            )

            return response

        except Exception as e:
            logger.error(f"Error selecting files: {str(e)}")
            return None

    def save_selection_results(self, repo_url: str, selection: FileSelectionResult):
        """Save file selection results to database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute(
                """UPDATE repositories 
                   SET selected_files = %s,
                       selection_criteria = %s,
                       selected_at = %s
                   WHERE url = %s""",
                (json.dumps(selection.selected_files),
                 json.dumps(selection.selection_criteria),
                 datetime.now(),
                 repo_url)
            )
            
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving selection results: {str(e)}")

    def run(self):
        """Main service loop."""
        logger.info("File Selection Service started. Waiting for messages...")
        try:
            for message in self.consumer:
                data = message.value
                repo_url = data.get('repo_url')
                repo_path = data.get('repo_path')
                task = data.get('task')

                if task == 'select_files' and repo_url and repo_path:
                    logger.info(f"Selecting files from repository: {repo_url}")
                    
                    # Update status
                    self.update_repository_status(repo_url, 'FILE_SELECTION')
                    
                    # Perform file selection
                    selection = self.select_files(repo_path)
                    
                    if selection:
                        # Save results
                        self.save_selection_results(repo_url, selection)
                        self.update_repository_status(repo_url, 'FILES_SELECTED')
                        
                        # Send next task to RAG loading service
                        self.producer.send('repository.tasks', {
                            'repo_url': repo_url,
                            'repo_path': repo_path,
                            'task': 'load_rag',
                            'selected_files': selection.selected_files
                        })
                        
                        # Send status update
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'FILES_SELECTED',
                            'selection': selection.dict()
                        })
                    else:
                        error_msg = "File selection failed"
                        self.update_repository_status(repo_url, 'FILE_SELECTION_FAILED', error_msg)
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'FILE_SELECTION_FAILED',
                            'error': error_msg
                        })

        except KeyboardInterrupt:
            logger.info("Shutting down File Selection Service...")

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
    service = FileSelectionService(kafka_config['bootstrap_servers'], db_config)
    service.run()