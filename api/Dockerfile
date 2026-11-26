# Image tag must match the playwright version pinned below (browsers are baked in).
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "playwright==1.62.0"
COPY tps ./tps
COPY api ./api
RUN mkdir -p data logs output && chown pwuser:pwuser data logs output
USER pwuser
ENV OUTPUT_DIR=/app/output
EXPOSE 8000
# --no-access-log: the page polls GET /api/job every second, which would flood the log.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
