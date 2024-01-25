## Use the official Python image
#FROM python:3.11
#
## Set the working directory
#WORKDIR /usr/src/app
#
## Copy requirements file and install dependencies
#COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt
#
## Copy the rest of the application code
#COPY . .
#
## Install cron and create a cron job
#RUN apt-get update && apt-get -y install cron
#RUN echo "0 3 * * * root /usr/src/app/main.py >> /var/log/cron.log 2>&1" > /etc/cron.d/playwright-cron
#RUN chmod 0644 /etc/cron.d/playwright-cron
#
## Create the log file
#RUN touch /var/log/cron.log
#
## Run cron in the foreground
#CMD cron && tail -f /var/log/cron.log


# Use the official Python image
FROM python:3.11

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers
RUN playwright install

# Copy the rest of the application code
COPY . .

# Run main.py
CMD ["python", "main.py"]