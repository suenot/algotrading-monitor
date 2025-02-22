import os
import json
import logging
from typing import Optional, Dict, Any, List
from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
import psycopg2

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.document_loaders import TextLoader

from core.logger import get_logger

logger = get_logger(__name__, level=logging.INFO, log_to_file=True)

class RAGLoadingService:
    """Service for loading repository files into RAG system using LangChain."""

    def __init__(self, kafka_bootstrap_servers: str, db_config: Dict[str, Any]):
        self.consumer = KafkaConsumer(
            'repository.tasks',
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='rag-loading-service'
        )
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        self.db_config = db_config
        self.vector_store = None

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

    def load_files_to_rag(self, repo_path: str, selected_files: List[str]) -> bool:
        """Load selected files into RAG system using LangChain."""
        try:
            # Initialize text splitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

            documents = []
            for file_path in selected_files:
                full_path = os.path.join(repo_path, file_path)
                if os.path.exists(full_path):
                    try:
                        loader = TextLoader(full_path)
                        file_documents = loader.load()
                        split_docs = text_splitter.split_documents(file_documents)
                        documents.extend(split_docs)
                    except Exception as e:
                        logger.error(f"Error processing file {file_path}: {str(e)}")

            if documents:
                # Initialize vector store
                embeddings = OpenAIEmbeddings()
                self.vector_store = Chroma.from_documents(
                    documents=documents,
                    embedding=embeddings,
                    persist_directory=os.path.join(repo_path, '.vectorstore')
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Error loading files to RAG: {str(e)}")
            return False

    def run(self):
        """Main service loop."""
        logger.info("RAG Loading Service started. Waiting for messages...")
        try:
            for message in self.consumer:
                data = message.value
                repo_url = data.get('repo_url')
                repo_path = data.get('repo_path')
                task = data.get('task')
                selected_files = data.get('selected_files', [])

                if task == 'load_rag' and repo_url and repo_path and selected_files:
                    logger.info(f"Loading files to RAG for repository: {repo_url}")
                    
                    # Update status
                    self.update_repository_status(repo_url, 'LOADING_RAG')
                    
                    # Load files to RAG
                    success = self.load_files_to_rag(repo_path, selected_files)
                    
                    if success:
                        # Update status
                        self.update_repository_status(repo_url, 'RAG_LOADED')
                        
                        # Send next task for analysis
                        self.producer.send('repository.tasks', {
                            'repo_url': repo_url,
                            'repo_path': repo_path,
                            'task': 'analyze'
                        })
                        
                        # Send status update
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'RAG_LOADED'
                        })
                    else:
                        error_msg = "RAG loading failed"
                        self.update_repository_status(repo_url, 'RAG_LOADING_FAILED', error_msg)
                        self.producer.send('repository.status', {
                            'repo_url': repo_url,
                            'status': 'RAG_LOADING_FAILED',
                            'error': error_msg
                        })

        except KeyboardInterrupt:
            logger.info("Shutting down RAG Loading Service...")

if __name__ == "__main__":
    # Configuration
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
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
    
    # Start the service
    service = RAGLoadingService(kafka_config['bootstrap_servers'], db_config)
    service.run()