import sqlite3
import os

DATABASE_URL = "udip.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        project_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        files_uploaded INTEGER NOT NULL,
        records_processed INTEGER NOT NULL,
        quality_score INTEGER,
        processing_time TEXT,
        project_data TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Create mapping_templates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mapping_templates (
        template_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        template_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mapping_json TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Create project_history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_history (
        project_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        project_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        files_uploaded INTEGER NOT NULL,
        records_processed INTEGER NOT NULL,
        quality_score INTEGER,
        processing_time TEXT,
        project_data TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Create api_keys table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        api_key TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Create automation_rules table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS automation_rules (
        rule_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        rule_name TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        webhook_url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

# Initialize the database when the module is imported
init_db()
