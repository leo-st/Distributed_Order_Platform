FROM python:3.12-slim

# /code is the Python root; the app lives at /code/app so `from app.x` works
WORKDIR /code

RUN pip install --no-cache-dir poetry==1.8.5 && \
    poetry config virtualenvs.create false

# Copy dependency files first for better layer caching
COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --only main --no-interaction

# Copy app source (overridden by the volume mount in docker-compose during dev)
COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
