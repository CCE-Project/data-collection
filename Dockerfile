# Use an official Python runtime as a base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app/
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variables if needed
# ENV ENV_VAR_NAME=value

# Run the Playwright scrape job
CMD ["python", "main.py"]

# Example: Run the job every day at 3 AM
# To customize the CRON schedule, you can use an online CRON expression generator
# For example, "0 3 * * *" represents every day at 3 AM
RUN echo "0 3 * * * /usr/src/app/scrape_script.py" > /etc/cron.d/playwright-cron

# Give execution rights to the cron job
RUN chmod 0644 /etc/cron.d/playwright-cron

# Apply cron job
RUN crontab /etc/cron.d/playwright-cron

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD cron && tail -f /var/log/cron.log
