FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py .

RUN mkdir -p /data

# По умолчанию данные в /data (смонтируйте volume при необходимости)
ENV BOT_DATA_FILE=/data/bot_data.json

CMD ["python", "bot.py"]
