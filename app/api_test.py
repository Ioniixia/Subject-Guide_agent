"""A tiny app for trying the agent endpoints before the main FastAPI app (api.py) exists.

    uvicorn api_test:app --app-dir app --reload      then open http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from agent_routes import router

app = FastAPI(title="Study agent API (test)")
app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}

