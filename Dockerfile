# One container: the FastAPI backend (with the agents) serving the built React frontend.
# Works on Hugging Face Spaces (Docker) and on any host that runs Docker. Port 7860.

# ---- 1. Build the React frontend ----
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. Python runtime ----
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# CPU-only PyTorch: the default wheel is several GB larger and a free host has no GPU
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt python-multipart \
    && pip uninstall -y torchvision

# Download the embedding model once, at build time, so the first request is not slow
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    && chmod -R a+rX /opt/hf-cache

COPY . .
COPY --from=frontend /build/dist ./frontend/dist
RUN mkdir -p data logs && chown -R user:user /home/user/app

USER user
ENV PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "app", "--host", "0.0.0.0", "--port", "7860"]
