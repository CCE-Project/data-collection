# For Linux based systems
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

# For Windows based systems
#FROM mcr.microsoft.com/windows/python:3.11-windowsservercore-ltsc2022
#
#WORKDIR C:/app
#
#COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt
#
#COPY . .
#
#RUN echo schtasks /create /tn "PlaywrightTask" /tr "C:\app\python.exe C:\app\main.py" /sc daily /st 03:00 /F >> run_tasks.bat
#RUN run_tasks.bat

# For MacOS
#FROM python:3.11
#
#WORKDIR /usr/src/app
#
#COPY requirements.txt .
#
#RUN pip install --no-cache-dir -r requirements.txt
#
#COPY . .
#
#CMD ["python", "main.py"]
