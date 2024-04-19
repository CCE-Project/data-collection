# Use Python base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies
RUN apt-get update && apt-get -y install cron

# Copy the application code
COPY . .

# Set the PYTHONUNBUFFERED environment variable
ENV PYTHONUNBUFFERED=1

# Ensure scripts have execute permissions
RUN chmod +x /usr/src/app/*.py

# Copy and run the setup script
COPY setup_cron.sh /usr/src/app/setup_cron.sh
RUN chmod +x /usr/src/app/setup_cron.sh

# Create the log file
RUN touch /var/log/cron.log

# Set up cron jobs
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-today-news && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-us && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-politics && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-2024-election && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-health && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-science && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-the360 && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-today-news && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-us && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-politics && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-2024-election && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-health && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-science && \
    echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-the360

# Give execution permissions to cron jobs
RUN chmod 0644 /etc/cron.d/playwright-cron-*

# Run cron in the foreground
CMD ["cron", "-f"]
