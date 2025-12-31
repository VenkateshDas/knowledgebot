-- PostgreSQL Initialization Script for LightRAG
-- Auto-runs when PostgreSQL container starts

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create database if needed (usually already exists)
-- CREATE DATABASE lightrag_prod;

-- Show installed extensions
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- Grant permissions (if using non-default user)
-- GRANT ALL PRIVILEGES ON DATABASE lightrag_prod TO postgres;

-- Log success
DO $$
BEGIN
    RAISE NOTICE 'pgvector extension enabled successfully';
END $$;
