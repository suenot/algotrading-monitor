import os
import json
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from github import Github
from kafka import KafkaProducer
import psycopg2
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

class SearchConfig(BaseModel):
    """Configuration for repository search"""
    tags: List[str]
    min_stars: int = 0
    min_forks: int = 0
    language: Optional[str] = None
    created_after: Optional[str] = None

class ProjectDiscoveryService:
    def __init__(self, github_token: str, kafka_bootstrap_servers: str, db_config: Dict):
        self.github_client = Github(github_token)
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        self.db_config = db_config
        self.setup_logging()

    def setup_logging(self):
        """Configure logging settings"""
        logger.add(
            "logs/project_discovery.log",
            rotation="1 day",
            retention="7 days",
            level="INFO"
        )

    def is_repository_analyzed(self, repo_url: str) -> bool:
        """Check if repository was already analyzed"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM repositories WHERE url = %s",
                        (repo_url,)
                    )
                    result = cur.fetchone()
                    return result is not None
        except Exception as e:
            logger.error(f"Database error checking repository status: {e}")
            return False

    def save_repository(self, repo_url: str, metadata: Dict) -> None:
        """Save repository to database"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO repositories 
                        (url, metadata, status, created_at) 
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING""",
                        (repo_url, json.dumps(metadata), 'DISCOVERED', datetime.now())
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Database error saving repository: {e}")

    def search_repositories(self, config: SearchConfig) -> None:
        """Search for repositories based on configured tags"""
        try:
            for tag in config.tags:
                query = f"{tag} in:readme,description,topics"
                if config.language:
                    query += f" language:{config.language}"
                if config.min_stars > 0:
                    query += f" stars:>={config.min_stars}"
                if config.min_forks > 0:
                    query += f" forks:>={config.min_forks}"
                if config.created_after:
                    query += f" created:>={config.created_after}"

                logger.info(f"Searching repositories with query: {query}")
                repositories = self.github_client.search_repositories(query)

                for repo in repositories:
                    if self.is_repository_analyzed(repo.html_url):
                        logger.debug(f"Repository already analyzed: {repo.html_url}")
                        continue

                    metadata = {
                        'name': repo.name,
                        'description': repo.description,
                        'stars': repo.stargazers_count,
                        'forks': repo.forks_count,
                        'language': repo.language,
                        'topics': repo.get_topics(),
                        'created_at': repo.created_at.isoformat(),
                        'updated_at': repo.updated_at.isoformat()
                    }

                    # Save to database
                    self.save_repository(repo.html_url, metadata)

                    # Send to Kafka for processing
                    self.producer.send('repository.tasks', {
                        'repo_url': repo.html_url,
                        'task': 'analyze',
                        'metadata': metadata
                    })
                    logger.info(f"Discovered new repository: {repo.html_url}")

                # Respect GitHub API rate limits
                time.sleep(2)

        except Exception as e:
            logger.error(f"Error during repository search: {e}")

    def run(self, interval_minutes: int = 60):
        """Run the service with specified interval"""
        logger.info("Starting Project Discovery Service")
        
        while True:
            try:
                # Default configuration for algotrading projects
                config = SearchConfig(
                    tags=['algorithmic-trading', 'trading-bot', 'trading-strategy'],
                    min_stars=5,
                    min_forks=2,
                    created_after=(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                )
                
                self.search_repositories(config)
                logger.info(f"Waiting {interval_minutes} minutes until next search...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("Shutting down Project Discovery Service...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    load_dotenv()

    # Configuration
    github_token = os.getenv('GITHUB_TOKEN')
    kafka_config = {
        'bootstrap_servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS')
    }
    db_config = {
        'dbname': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'host': os.getenv('DB_HOST'),
        'port': os.getenv('DB_PORT')
    }

    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is required")
        exit(1)

    # Start the service
    service = ProjectDiscoveryService(
        github_token=github_token,
        kafka_bootstrap_servers=kafka_config['bootstrap_servers'],
        db_config=db_config
    )
    service.run()