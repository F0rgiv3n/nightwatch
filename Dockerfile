FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (so Docker can cache this layer).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app.
COPY sentinel.py config.yaml ./

# NTFY_TOPIC must be provided at runtime, e.g.:
#   docker run -e NTFY_TOPIC=my-topic sentinel
CMD ["python", "sentinel.py"]
