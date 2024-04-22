FROM python:3.11-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers
RUN playwright install

# Install dependencies for Playwright
RUN playwright install-deps

# Copy the application code
COPY . .

# Set the PYTHONUNBUFFERED environment variable
ENV PYTHONUNBUFFERED=1

# Ensure scripts have execute permissions
RUN chmod +x /usr/src/app/*.py

# Install cron
RUN apt-get update && apt-get -y install cron

# Copy and run the setup script
COPY setup_cron.sh /usr/src/app/setup_cron.sh
RUN chmod +x /usr/src/app/setup_cron.sh
CMD /usr/src/app/setup_cron.sh
