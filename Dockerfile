FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
COPY static ./static

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

USER app

EXPOSE 8080

CMD ["sh", "-c", "uvicorn paradise_park_sales_agent.api:app --host 0.0.0.0 --port ${PORT}"]
