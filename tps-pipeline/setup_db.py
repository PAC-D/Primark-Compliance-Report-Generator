#!/usr/bin/env python3
"""Setup PostgreSQL database for TPS Pipeline."""

import subprocess
import sys

def run_cmd(cmd, check=True):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise SystemExit(f"Command failed: {cmd}")
    return result

def main():
    print("=== TPS Pipeline Database Setup ===\n")

    # 1. Create the database
    print("1. Creating database 'tps_compliance'...")
    run_cmd('sudo -u postgres psql -c "DROP DATABASE IF EXISTS tps_compliance;"')
    run_cmd('sudo -u postgres psql -c "CREATE DATABASE tps_compliance;"')

    # 2. Update config.yaml with connection settings
    print("\n2. Updating config.yaml...")
    config_content = """database:
  host: localhost
  port: 5432
  name: tps_compliance
  user: postgres
  password: "postgres"

paths:
  data_dir: data
  output_dir: output

app:
  report_month_offset: 1
"""
    with open("config.yaml", "w") as f:
        f.write(config_content)
    print("config.yaml updated (user: postgres, password: postgres)")

    # 3. Run init_db
    print("\n3. Initializing database schema...")
    sys.path.insert(0, ".")
    from database import init_db
    init_db()
    print("Database schema created.")

    print("\n=== Setup complete ===")
    print("Run 'source .venv/bin/activate && python menu.py' to start.")

if __name__ == "__main__":
    main()