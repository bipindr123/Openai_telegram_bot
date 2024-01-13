FROM python:3.10.13-slim-bookworm
RUN apt-get update -y && apt-get install -y build-essential

#use --build-arg LIB_DIR=/usr/lib for arm64 cpus

WORKDIR /app

ADD bot.py /app/bot.py
ADD .env /app/.env

ADD requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT ["python3","bot.py"]
