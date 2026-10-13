FROM node:22-slim AS mcp
WORKDIR /opt/mui-mcp
RUN npm install @mui/mcp@0.1.7

FROM python:3.11-slim
WORKDIR /app

COPY --from=mcp /usr/local/bin/node /usr/local/bin/node
COPY --from=mcp /opt/mui-mcp /opt/mui-mcp

ENV MUI_MCP_ENTRY=/opt/mui-mcp/node_modules/@mui/mcp/stdio.js PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]

