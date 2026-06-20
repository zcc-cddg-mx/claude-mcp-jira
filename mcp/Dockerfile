FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp/ ./mcp/
COPY certs/ ./certs/

EXPOSE 8001

CMD ["python", "-m", "mcp.server"]
