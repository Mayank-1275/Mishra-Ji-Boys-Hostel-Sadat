"""
One-time script to create all database tables from schema.sql.
Run this ONCE from the terminal:  python setup_database.py
It reads your connection details from .streamlit/secrets.toml
"""

import tomli
import mysql.connector

# 1. Read the secret settings file.
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomli.load(f)

db = secrets["db"]

# 2. Read the schema file (all the CREATE TABLE commands).
with open("schema.sql", "r", encoding="utf-8") as f:
    schema_sql = f.read()

# 3. Connect to the cloud database.
print("Connecting to the database...")
conn = mysql.connector.connect(
    host=db["host"],
    port=db["port"],
    user=db["user"],
    password=db["password"],
    database=db["database"],
)
cursor = conn.cursor()

# 4. Run every command in the schema file, one by one.
print("Creating tables...")
statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
for statement in statements:
    cursor.execute(statement)

conn.commit()

# 5. Show which tables now exist, as proof it worked.
cursor.execute("SHOW TABLES;")
tables = cursor.fetchall()
print("\nDone! Tables in your database:")
for t in tables:
    print("  -", t[0])

cursor.close()
conn.close()
print("\nDatabase setup complete.")