FROM python:3.11-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements file and install dependencies
COPY requirements.txt .

# Install dependencies, playwright browsers, and cron
RUN set -eux; \
    apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install playwright && \
    playwright install && \
    playwright install-deps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    # Copy the application code
    apt-get update && \
    apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set the PYTHONUNBUFFERED environment variable
ENV PYTHONUNBUFFERED=1

# Copy the application code
COPY . .

# Set execute permissions for setup script and define CMD
COPY setup_cron.sh .
RUN chmod +x setup_cron.sh
CMD ./setup_cron.sh
