"""A tiny app for trying the agent endpoints before the main FastAPI app (api.py) exists.

    uvicorn api_test:app --app-dir app --reload      then open http://localhost:8000/docs
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_routes import router

app = FastAPI(title="Study agent API (test)")

# A browser frontend on another address (http://localhost:5173) needs CORS to call the API.
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
