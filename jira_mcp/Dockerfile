FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jira_mcp/ ./jira_mcp/
COPY shared/ ./shared/
COPY certs/ ./certs/
COPY certs/ /etc/ssl/certs/
RUN cp /etc/ssl/certs/zurichseguros-rootca-until-2031_03_20.crt /etc/ssl/certs/zurich-root-ca.crt

EXPOSE 8001

CMD ["python", "-m", "jira_mcp.server"]
