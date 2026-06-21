"""
Script: start_dashboard.py
Description: Python wrapper to run the Streamlit dashboard. 
             This allows you to launch the dashboard simply by hitting the "Run" button in your IDE.
"""

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    # Resolve the paths dynamically relative to this script's location
    project_dir = Path(__file__).parent
    app_path = project_dir / "ui" / "04_app.py"
    
    print("Starting Streamlit Dashboard from Python...")
    print(f"Target App: {app_path}")
    print("Address:    http://localhost:8501")
    print("=" * 50)
    
    try:
        # Spawn Streamlit as a subprocess under the current Python interpreter
        subprocess.run([
            sys.executable,
            "-m", "streamlit", "run",
            str(app_path),
            "--server.port", "8501",
            "--server.address", "localhost",
            "--server.headless", "false"
        ])
    except KeyboardInterrupt:
        print("\nDashboard stopped gracefully.")
