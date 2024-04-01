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

# Create cron jobs with output redirection

# Articles scraper cron jobs

# Today News
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-today-news
# US
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-us
# Politics
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-politics
# 2024 Election
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-2024-election
# Health
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-health
# Science
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-science
# The360
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-the360


# Testing reply network
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/comment_reply_network_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-reply-network


# Users scraper cron jobs

# Today News
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-today-news
# US
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-us
# Politics
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-politics
# 2024 Election
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-2024-election
# Health
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-health
# Science
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-science
# The360
RUN echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-the360

# Give execution permissions to cron jobs
RUN chmod 0644 /etc/cron.d/playwright-cron-*

# Create the log file
RUN touch /var/log/cron.log

# Run cron in the foreground
CMD cron && tail -f /var/log/cron.log
