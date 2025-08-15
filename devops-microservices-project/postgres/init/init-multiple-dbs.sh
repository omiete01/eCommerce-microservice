#!/bin/bash
set -e

# Create databases and users
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE user_db;
    CREATE DATABASE product_db;

    CREATE USER user_service WITH ENCRYPTED PASSWORD 'userpassword';
    CREATE USER product_service WITH ENCRYPTED PASSWORD 'productpassword';

    GRANT ALL PRIVILEGES ON DATABASE user_db TO user_service;
    GRANT ALL PRIVILEGES ON DATABASE product_db TO product_service;
EOSQL

# Grant schema permissions per database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "user_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO user_service;
    
    -- Enable pg_stat_statements extension for user_db
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    
    -- Grant monitoring permissions
    GRANT pg_read_all_stats TO user_service;
    GRANT pg_read_all_stats TO product_service;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "product_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO product_service;
    
    -- Enable pg_stat_statements extension for product_db
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    
    -- Grant monitoring permissions
    GRANT pg_read_all_stats TO user_service;
    GRANT pg_read_all_stats TO product_service;
EOSQL

# Enable pg_stat_statements in postgres database for system-wide stats
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EOSQL