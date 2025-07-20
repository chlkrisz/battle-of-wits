FROM python:3.9-slim
WORKDIR /app
COPY requirements .
RUN apt-get update && apt-get install -y ffmpeg && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
ENV FLASK_APP=wits.py

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "wits:app"]