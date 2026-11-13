"""Vercel/FastAPI entry point; also `uv run uvicorn app:app` locally."""
from l1_lab.api import app

__all__ = ["app"]
