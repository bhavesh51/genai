# Project 7 – Legal Document Analysis & Contract Intelligence
# UBI9 Python base for OpenShift AI compatibility
FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="legal-document-analysis" \
      version="1.0.0" \
      description="AI-powered legal document analysis and contract intelligence on RHOAI 3.x" \
      io.openshift.tags="genai,legal,contract-intelligence,llm,weaviate" \
      maintainer="platform-team@enterprise.com"

USER 0

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Non-root user for OpenShift
RUN chown -R 1001:0 /app && chmod -R g=u /app
USER 1001

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--proxy-headers"]
