"""
CertiTrust - entry point.

Run with:
    python run.py

The Flask development server will start on http://localhost:5000
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
