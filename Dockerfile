FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.8
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY data ./data
COPY migrations ./migrations
COPY docs/learning ./docs/learning
COPY docs/architecture ./docs/architecture
COPY app.py ./
RUN uv sync --locked --no-dev --extra lab
ENV PATH="/app/.venv/bin:$PATH" LAB_STATE_DIR=/state
RUN useradd --create-home lab && mkdir /state && chown lab:lab /state
USER lab
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
