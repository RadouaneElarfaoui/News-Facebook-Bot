FROM python:3.12-slim

# Librairies système requises pour Pillow + rendu texte arabe RTL natif (libraqm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libraqm0 \
    libfribidi0 \
    libharfbuzz0b \
    libfontconfig1 \
    libjpeg62-turbo \
    zlib1g \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non-root
RUN useradd -m -u 1000 bot

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=bot:bot . .

RUN mkdir -p /app/data /app/data/agy-home /app/data/agy-workspace /app/output /app/logs \
    && chown -R bot:bot /app/data /app/output /app/logs

USER bot

ENV PYTHONUNBUFFERED=1 \
    AGY_BINARY=/usr/local/bin/agy \
    AGY_HOME=/app/data/agy-home

CMD ["python", "main.py", "--schedule"]
