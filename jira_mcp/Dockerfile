FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jira_mcp/ ./jira_mcp/
COPY shared/ ./shared/
COPY certs/ ./certs/

# Convertir DER→PEM y añadir al trust store del sistema
RUN openssl x509 -inform DER -in certs/zurichseguros-rootca-until-2031_03_20.crt \
        -out /usr/local/share/ca-certificates/zurich-root-ca.crt && \
    cp certs/localCA.crt /usr/local/share/ca-certificates/zurich-local-ca.crt && \
    update-ca-certificates

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8001

CMD ["python", "-m", "jira_mcp.server"]
