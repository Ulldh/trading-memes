FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libomp-dev \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

COPY . .

# Nginx config: reverse proxy on 8501 -> Streamlit on 8502
RUN rm -f /etc/nginx/sites-enabled/default && \
    cp nginx.conf /etc/nginx/conf.d/default.conf

RUN mkdir -p data/raw data/processed data/models .cache logs signals

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
# Nginx needs write access to its runtime dirs
RUN chown -R appuser:appuser /var/log/nginx /var/lib/nginx /run

USER appuser

CMD ["bash", "-c", "python scripts/download_models.py && streamlit run dashboard/app.py --server.port=8502 --server.address=127.0.0.1 & nginx -g 'daemon off;'"]
