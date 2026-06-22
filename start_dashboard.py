"""
Script: start_dashboard.py
Description: Python wrapper to run the Streamlit dashboard. 
             This allows you to launch the dashboard simply by hitting the "Run" button in your IDE.
"""

import subprocess
import sys
import socket
from pathlib import Path


def find_free_port(start: int = 8501, end: int = 8599) -> int:
    """Return the first available port in the given range."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
    raise RuntimeError(f"No free port found in range {start}-{end}")

if __name__ == "__main__":
    # Resolve the paths dynamically relative to this script's location
    project_dir = Path(__file__).parent
    app_path = project_dir / "ui" / "04_app.py"

    port = find_free_port()

    print("Starting Streamlit Dashboard from Python...")
    print(f"Target App: {app_path}")
    print(f"Address:    http://localhost:{port}")
    print("=" * 50)

    try:
        # Spawn Streamlit as a subprocess under the current Python interpreter
        subprocess.run([
            sys.executable,
            "-m", "streamlit", "run",
            str(app_path),
            "--server.port", str(port),
            "--server.address", "localhost",
            "--server.headless", "false"
        ])
    except KeyboardInterrupt:
        print("\nDashboard stopped gracefully.")
