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
RUN chmod +x /usr/src/app/articles_scraper.py /usr/src/app/users_scraper.py

# Install cron
RUN apt-get update && apt-get -y install cron

# Create cron jobs with output redirection
RUN echo "0 0 * * * root /usr/local/bin/python /usr/src/app/articles_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-12am
RUN echo "0 6 * * * root /usr/local/bin/python /usr/src/app/articles_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-6am
RUN echo "0 12 * * * root /usr/local/bin/python /usr/src/app/articles_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-12pm
RUN echo "0 18 * * * root /usr/local/bin/python /usr/src/app/articles_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-articles-6pm

RUN echo "0 0 * * * root /usr/local/bin/python /usr/src/app/users_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-12am
RUN echo "0 6 * * * root /usr/local/bin/python /usr/src/app/users_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-6am
RUN echo "0 12 * * * root /usr/local/bin/python /usr/src/app/users_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-12pm
RUN echo "0 18 * * * root /usr/local/bin/python /usr/src/app/users_scraper.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron-users-6pm

# Give execution permissions to cron jobs
RUN chmod 0644 /etc/cron.d/playwright-cron-*

# Create the log file
RUN touch /var/log/cron.log

# Run cron in the foreground
CMD cron && tail -f /var/log/cron.log
