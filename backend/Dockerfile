# Stage 1: Build Frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend (usiamo Python 3.11 per stabilità totale dei moduli binari)
FROM python:3.11-slim
WORKDIR /app

# Aggiorna pip per evitare problemi di risoluzione pacchetti
RUN pip install --no-cache-dir --upgrade pip

# Installa le dipendenze
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice del backend
COPY backend/main.py ./main.py

# Copia i file statici del frontend
COPY --from=frontend-build /app/frontend/dist ./static

# Copia l'intera cartella infra e la sotto-cartella static
COPY infra ./infra
COPY infra/.well-known ./static/.well-known

EXPOSE 10000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]