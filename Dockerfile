FROM python:3.7-slim-buster

COPY requirements.txt ./
RUN apt-get -qqy update && \
    pip3 install --no-cache-dir -r requirements.txt

WORKDIR /binance

COPY binance_producer.py .

ENTRYPOINT [ "python3" ]

EXPOSE 8080