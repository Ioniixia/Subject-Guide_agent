"""Serve the built React frontend from the same FastAPI app, so one address does everything."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    """Serve frontend/dist at '/'. Returns False (and mounts nothing) if the frontend was not built.
    Mount it after the API routes, so /ask, /docs and the others keep working."""
    if not (Path(dist) / "index.html").exists():
        return False
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    return True
