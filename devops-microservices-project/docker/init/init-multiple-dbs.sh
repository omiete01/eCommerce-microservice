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
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "product_db" <<-EOSQL
    GRANT ALL ON SCHEMA public TO product_service;
EOSQL
