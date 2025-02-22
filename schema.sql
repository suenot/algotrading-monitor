-- Database schema for algotrading-monitor

-- Repositories table to track processing status
CREATE TABLE repositories (
    id SERIAL PRIMARY KEY,
    url VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on url for faster lookups
CREATE INDEX idx_repositories_url ON repositories(url);

-- Create index on status for filtering
CREATE INDEX idx_repositories_status ON repositories(status);

-- Processing history table to track detailed status changes
CREATE TABLE processing_history (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id),
    status VARCHAR(50) NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

-- Create index on repository_id for faster joins
CREATE INDEX idx_processing_history_repo_id ON processing_history(repository_id);

-- Create index on created_at for time-based queries
CREATE INDEX idx_processing_history_created_at ON processing_history(created_at);

-- Comments for status values:
-- Status can be one of:
-- - 'PENDING': Initial state when URL is received
-- - 'CLONING': Repository is being cloned
-- - 'FILE_SELECTION': Important files are being selected
-- - 'RAG_LOADING': Files are being loaded into RAG
-- - 'ANALYZING': Project is being analyzed
-- - 'COMPLETED': Analysis is complete
-- - 'FAILED': Processing failed