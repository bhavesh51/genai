# Project 2 – Multi-Agent Platform
FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="multi-agent-platform" \
      version="1.0.0" \
      description="LangGraph multi-agent platform for RHOAI 3.x" \
      io.openshift.tags="genai,agent,langgraph"

USER 0
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN chown -R 1001:0 /app && chmod -R g=u /app
USER 1001

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4", "--proxy-headers"]
