# Kafka Message Design

## Topics

1. **repository.discovery**
   - Purpose: New repositories discovered for analysis
   - Message structure:
     ```json
     {
       "repository_url": "string",
       "discovery_timestamp": "ISO-8601 timestamp",
       "priority": "integer (1-5)",
       "source": "string (e.g., 'automatic', 'manual')"
     }
     ```

2. **repository.tasks**
   - Purpose: Tasks for repository processing
   - Message structure:
     ```json
     {
       "task_id": "UUID",
       "repository_url": "string",
       "task_type": "string (clone|select_files|load_rag|analyze)",
       "created_at": "ISO-8601 timestamp",
       "status": "string (pending|in_progress|completed|failed)",
       "metadata": {
         "priority": "integer (1-5)",
         "retry_count": "integer",
         "last_error": "string (optional)"
       }
     }
     ```

3. **repository.status**
   - Purpose: Status updates for repository processing
   - Message structure:
     ```json
     {
       "repository_url": "string",
       "status": "string (cloning|file_selection|rag_loaded|analyzed)",
       "timestamp": "ISO-8601 timestamp",
       "details": {
         "stage_duration": "integer (milliseconds)",
         "error": "string (optional)",
         "progress": "float (0-100)"
       }
     }
     ```

## Message Flow

1. **Project Discovery Flow**
   ```
   Project Discovery Service -> repository.discovery -> Git Cloning Service
   ```

2. **Processing Flow**
   ```
   Git Cloning Service -> repository.tasks (clone) ->
   File Selection Service -> repository.tasks (select_files) ->
   RAG Loading Service -> repository.tasks (load_rag) ->
   Project Analysis Service -> repository.tasks (analyze)
   ```

3. **Status Updates Flow**
   ```
   All Services -> repository.status -> Database Service
   ```

## Consumer Groups

1. **discovery-consumers**
   - Subscribes to: repository.discovery
   - Services: Git Cloning Service

2. **task-consumers**
   - Subscribes to: repository.tasks
   - Services: All processing services based on task_type

3. **status-consumers**
   - Subscribes to: repository.status
   - Services: Database Service

## Configuration

1. **Partitioning**
   - repository.discovery: 3 partitions
   - repository.tasks: 5 partitions
   - repository.status: 3 partitions

2. **Retention**
   - repository.discovery: 7 days
   - repository.tasks: 14 days
   - repository.status: 30 days

3. **Replication**
   - All topics: 3 replicas for high availability

## Error Handling

1. **Dead Letter Queue**
   - Topic: repository.dlq
   - Purpose: Store messages that failed processing
   - Retention: 30 days

2. **Retry Policy**
   - Maximum retries: 3
   - Retry delay: Exponential backoff (1min, 5min, 15min)

## Monitoring

1. **Metrics to Track**
   - Message throughput
   - Consumer lag
   - Processing time per message
   - Error rate
   - Retry count

2. **Alerts**
   - Consumer lag > 1000 messages
   - Error rate > 5%
   - Processing time > 30 seconds