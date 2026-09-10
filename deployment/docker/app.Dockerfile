FROM python:3.11-slim-bookworm

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY junction ./junction
COPY public ./public

RUN mkdir -p /opt/antithesis/catalog \
    && ln -s /app/junction /opt/antithesis/catalog/junction

CMD ["python", "-m", "junction.node", "--id", "north"]
