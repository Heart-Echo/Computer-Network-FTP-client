-- FTP Client Database Initialization Script
-- Database: PostgreSQL
-- Usage: psql -U postgres -d ftp_client -f init_db.sql

-- Connection history table
CREATE TABLE IF NOT EXISTS connection_history (
    id SERIAL PRIMARY KEY,
    host VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 21,
    username VARCHAR(100),
    connection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnect_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'connected'
);

-- Transfer records table
CREATE TABLE IF NOT EXISTS transfer_records (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER REFERENCES connection_history(id),
    transfer_type VARCHAR(10) NOT NULL,
    remote_file VARCHAR(500) NOT NULL,
    local_path VARCHAR(500) NOT NULL,
    file_size BIGINT DEFAULT 0,
    transferred_bytes BIGINT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'in_progress',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    resume_supported BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resume points table (for broken transfer resumption)
CREATE TABLE IF NOT EXISTS resume_points (
    id SERIAL PRIMARY KEY,
    transfer_id INTEGER REFERENCES transfer_records(id) ON DELETE CASCADE,
    byte_offset BIGINT NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(transfer_id)
);

-- Favorite servers table
CREATE TABLE IF NOT EXISTS favorite_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 21,
    username VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(host, port, username)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_connection_history_host 
    ON connection_history(host);
CREATE INDEX IF NOT EXISTS idx_transfer_records_connection 
    ON transfer_records(connection_id);
CREATE INDEX IF NOT EXISTS idx_transfer_records_status 
    ON transfer_records(status);
CREATE INDEX IF NOT EXISTS idx_resume_points_transfer 
    ON resume_points(transfer_id);