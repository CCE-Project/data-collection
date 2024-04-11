FROM python:3.11

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

# Create the log file
RUN touch /var/log/cron.log

# Create cron jobs and run them
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-today-news \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-us \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-politics \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-2024-election \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-health \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-science \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-the360 \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-today-news \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-us \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-politics \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-2024-election \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-health \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-science \
    && echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-the360 \
    && chmod 0644 /etc/cron.d/playwright-cron-* \
    && cron

# Clean up space
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# Run cron in the foreground
CMD ["cron", "-f"]
