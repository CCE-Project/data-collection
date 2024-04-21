FROM python:3.11-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers and dependencies
RUN playwright install && \
    playwright install-deps

# Copy the application code
COPY . .

# Set the PYTHONUNBUFFERED environment variable
ENV PYTHONUNBUFFERED=1

# Ensure scripts have execute permissions
RUN chmod +x *.py

# Install cron
RUN apt-get update && apt-get -y install cron

# Copy and run the setup script
COPY setup_cron.sh .
RUN chmod +x setup_cron.sh && \
    ./setup_cron.sh

# Clean up unnecessary artifacts and dependencies
RUN apt-get purge -y cron && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    rm -rf /usr/src/app/.git /usr/src/app/setup_cron.sh /usr/src/app/requirements.txt

# Create the log file
RUN touch /var/log/cron.log

# Run cron in the foreground
CMD cron && tail -f /var/log/cron.log
