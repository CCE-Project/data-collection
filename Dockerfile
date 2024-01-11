FROM python:3.11

WORKDIR /usr/src/app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]

RUN echo "0 3 * * * /usr/src/app/main.py" > /etc/cron.d/playwright-cron

RUN chmod 0644 /etc/cron.d/playwright-cron

RUN crontab /etc/cron.d/playwright-cron

RUN touch /var/log/cron.log

CMD cron && tail -f /var/log/cron.log
