FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN pip install --no-cache-dir .

ENV ZOTERO_API_KEY=""
ENV ZOTERO_USER_ID=""

ENTRYPOINT ["zotero-mcp"]
