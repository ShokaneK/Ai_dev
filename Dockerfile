# MCP server for the Patch & Task Compliance Assistant.
# Exposes Jira + the comparison engine as tools Claude/n8n can call over HTTP.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY comparison_engine.py jira_client.py mcp_server.py ./

# Config is passed in at runtime via env vars (see docker-compose.yml / README):
#   ANTHROPIC_API_KEY, JIRA_BASE_URL, JIRA_AUTH_MODE, JIRA_PAT (or JIRA_EMAIL + JIRA_API_TOKEN)

EXPOSE 8000

CMD ["python3", "mcp_server.py"]
