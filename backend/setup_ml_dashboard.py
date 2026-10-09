import os
import sys
from time import sleep

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.services.athena_service import AthenaService

athena = AthenaService()

# 1. Create database
try:
    print("Creating ml_dashboard database...")
    athena.run("CREATE DATABASE IF NOT EXISTS ml_dashboard;")
    print("Database ml_dashboard created.")
except Exception as e:
    print(f"Error creating DB: {e}")

tables_to_migrate = [
    "impressions",
    "clicks",
    "organic",
    "organic90",
    "training_data",
    "validation_data",
    "payload"
]

for table in tables_to_migrate:
    print(f"\nMigrating {table}...")
    try:
        # Get DDL from ml_dashboard
        res = athena.run(f"SHOW CREATE TABLE ml_dashboard.{table}")
        if not res:
            print(f"Table ml_dashboard.{table} not found.")
            continue
            
        key = list(res[0].keys())[0]
        ddl_lines = [key] + [list(row.values())[0] for row in res]
        ddl = "\n".join(ddl_lines)
        
        # Modify DDL to create in ml_dashboard
        ddl = ddl.replace(f"`ml_dashboard.{table}`", f"`ml_dashboard.{table}`")
        
        print(f"Running DDL for ml_dashboard.{table}...")
        athena.run(ddl)
        print(f"Successfully created ml_dashboard.{table}")
    except Exception as e:
        print(f"Failed to migrate {table}: {e}")
