FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY server /app/server

RUN pip install --no-cache-dir -e /app/server

EXPOSE 8080

CMD ["python", "-m", "msgraph_mcp"]
