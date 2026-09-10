FROM python:3.11-slim-bookworm

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY junction ./junction
COPY public ./public

ENV VISUALIZER_HOST=0.0.0.0
ENV DATA_DIR=/data

EXPOSE 8080
CMD ["python", "-m", "junction.launcher"]
