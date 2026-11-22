"""Deployment entry point: the full API (api.py) plus the built React frontend on one address.

    python -m uvicorn main:app --app-dir app --host 0.0.0.0 --port 7860
"""
from pathlib import Path

from api import app
from web import mount_frontend

mounted = mount_frontend(app, Path(__file__).resolve().parent.parent / "frontend" / "dist")
if not mounted:
    print("Note: frontend/dist was not found, so only the API is served. Run `npm run build` in frontend/.")
