FROM python:3.12-slim

WORKDIR /code

RUN pip install --no-cache-dir poetry==1.8.5 && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

RUN poetry install --no-root --only main --no-interaction

COPY notification_service ./notification_service
COPY shared ./shared

CMD ["python", "-m", "notification_service.main"]
