FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ENV PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers
RUN python -m playwright install-deps chromium
RUN python -m playwright install chromium

COPY . .

ENV PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers

CMD ["python", "miner.py"]