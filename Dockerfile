FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Security: don't run as root
RUN useradd -m -u 1000 appuser

# Set up writable dirs for HF Spaces
ENV HF_HOME=/tmp/huggingface
ENV STREAMLIT_HOME=/tmp/.streamlit
ENV NLTK_DATA=/tmp/nltk_data
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('cmudict', download_dir='/tmp/nltk_data')"

# Copy app code
COPY . .

# Create data dirs with proper permissions
RUN mkdir -p /app/data /app/logs /app/exports /tmp/.streamlit && \
    chown -R appuser:appuser /app /tmp/.streamlit /tmp/huggingface 2>/dev/null || true

# Streamlit config — XSRF protection enabled
RUN echo '[server]\nheadless = true\nport = 7860\nenableCORS = true\nenableXsrfProtection = true\n\n[theme]\nprimaryColor = "#1E88E5"\nbackgroundColor = "#ffffff"\nsecondaryBackgroundColor = "#f0f2f6"\ntextColor = "#262730"' > /tmp/.streamlit/config.toml

USER appuser

EXPOSE 7860

CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
