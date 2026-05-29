FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite DB lives in /data so it can be mounted as a persistent volume
RUN mkdir -p /data
ENV DB_PATH=/data/brewbot.db

CMD ["python", "app.py"]
