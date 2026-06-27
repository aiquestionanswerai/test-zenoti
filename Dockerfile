FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers
RUN python -m playwright install-deps chromium && \
    python -m playwright install chromium

COPY . .

CMD ["python", "-u", "miner.py"]