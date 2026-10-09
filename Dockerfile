# Stage 1: build the React SPA
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: FastAPI serving /api + the built SPA
FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PORT=8080 WEB_DIST=/srv/web/dist
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY --from=web /web/dist ./web/dist
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
