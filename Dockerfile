FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl wget gnupg ca-certificates fonts-liberation libnss3 \
    libatk-bridge2.0-0 libxss1 libasound2 libx11-xcb1 libgtk-3-0 \
    && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
