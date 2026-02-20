# Använd en lättviktig Python-image
FROM python:3.11-slim

# Sätt arbetskatalog
WORKDIR /app

# Installera systemberoenden för psycopg2 (behövs för PostgreSQL)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kopiera requirements först för att utnyttja Docker-cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiera resten av koden
COPY . .

# Exponera porten som Flask körs på
EXPOSE 5000

# Starta applikationen
CMD ["python", "app.py"]