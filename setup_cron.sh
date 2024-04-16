#!/bin/bash

# Define cron jobs
# Articles scraper cron jobs
# Today News
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-today-news
# US
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-us
# Politics
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-politics
# 2024 Election
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-2024-election
# Health
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-health
# Science
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-science
# The360
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-the360

# Users scraper cron jobs
# Today News
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_today_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-today-news
# US
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_us.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-us
# Politics
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_politics.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-politics
# 2024 Election
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_2024_election.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-2024-election
# Health
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_health.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-health
# Science
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_science.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-science
# The360
echo "0 0,6,12,18 * * * root /usr/local/bin/python /usr/src/app/users_scraper_the360.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-the360

# Give execution permissions to cron jobs
chmod 0644 /etc/cron.d/playwright-cron-*

# Create the log file
touch /var/log/cron.log

# Run cron in the foreground
cron && tail -f /var/log/cron.log
