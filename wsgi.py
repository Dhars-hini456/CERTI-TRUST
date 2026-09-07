"""CertiTrust - production WSGI entry point.

Used by production servers (gunicorn#, see Procfile:
    gunicorn wsgi:application

For local development, use `python run.py` instead.
"""
from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000)