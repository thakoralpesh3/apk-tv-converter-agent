FROM python:3.12-slim-bookworm

# Install OpenJDK 17 and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    aapt \
    zipalign \
    curl \
    wget \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN ./setup_tools.sh

EXPOSE 8877

ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8877

CMD ["python3", "agent.py", "--gui"]
