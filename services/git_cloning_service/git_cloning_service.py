import os
import git
from kafka import KafkaConsumer, KafkaProducer
import json
import psycopg2
from datetime import datetime

class GitCloningService:
    def __init__(self, kafka_bootstrap_servers, db_config):
        self.consumer = KafkaConsumer(
            'repository.discovery',
            bootstrap_servers=kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        self.db_config = db_config
        self.clone_dir = os.path.join(os.getcwd(), 'cloned_repos')
        os.makedirs(self.clone_dir, exist_ok=True)

    def update_repository_status(self, repo_url, status, error=None):
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
            print(f"Database error: {str(e)}")

    def clone_repository(self, repo_url):
        try:
            # Extract repository name from URL
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = os.path.join(self.clone_dir, repo_name)
            
            # Clone the repository
            git.Repo.clone_from(repo_url, repo_path)
            
            # Update status in database
            self.update_repository_status(repo_url, 'CLONED')
            
            # Send message to next service
            self.producer.send('repository.tasks', {
                'repo_url': repo_url,
                'repo_path': repo_path,
                'status': 'CLONED',
                'task': 'select_files'
            })
            
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"Error cloning repository {repo_url}: {error_msg}")
            self.update_repository_status(repo_url, 'CLONE_FAILED', error_msg)
            return False

    def run(self):
        print("Git Cloning Service started. Waiting for messages...")
        try:
            for message in self.consumer:
                repo_data = message.value
                repo_url = repo_data.get('repo_url')
                
                if repo_url:
                    print(f"Received cloning task for repository: {repo_url}")
                    self.clone_repository(repo_url)
                else:
                    print("Received message without repository URL")
        except KeyboardInterrupt:
            print("Shutting down Git Cloning Service...")

if __name__ == "__main__":
    # Configuration
    kafka_config = {
        'bootstrap_servers': 'localhost:9092'
    }
    
    db_config = {
        'dbname': 'algotrading_monitor',
        'user': 'postgres',
        'password': 'postgres',
        'host': 'localhost',
        'port': '5432'
    }
    
    # Start the service
    service = GitCloningService(kafka_config['bootstrap_servers'], db_config)
    service.run()