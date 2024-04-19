# Use a lightweight Python Alpine image
FROM python:3.11-alpine

# Set the working directory
WORKDIR /usr/src/app

# Copy only the requirements file
COPY requirements.txt .

# Install dependencies and clean up
RUN apk --no-cache add --virtual .build-deps gcc musl-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del .build-deps

# Install Playwright browsers and dependencies
RUN apk --no-cache add nodejs npm && \
    npm install -g playwright && \
    playwright install && \
    playwright install-deps

# Copy the application code
COPY . .

# Set the PYTHONUNBUFFERED environment variable
ENV PYTHONUNBUFFERED=1

# Ensure scripts have execute permissions
RUN chmod +x *.py

# Install cron and clean up
RUN apk --no-cache add cron && \
    rm -rf /var/cache/apk/*

# Copy and set up the cron script
COPY setup_cron.sh .
RUN chmod +x setup_cron.sh && \
    ./setup_cron.sh

# Create the log file
RUN touch /var/log/cron.log

# Run cron in the foreground and tail the log file
CMD ["crond", "-f", "-L", "/var/log/cron.log"]
