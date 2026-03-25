FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libomp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

COPY . .

RUN mkdir -p data/raw data/processed data/models .cache logs signals

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["bash", "-c", "python scripts/download_models.py && streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0"]
