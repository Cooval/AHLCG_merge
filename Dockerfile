FROM python:3.11-slim

WORKDIR /opt/app

# Skopiuj plik zależności
COPY requirements.txt .

# Zaktualizuj pip i zainstaluj wymagane paczki
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Skopiuj cały kod projektu
COPY . .

# Wystawienie portu dla serwera
EXPOSE 8000

# Uruchomienie aplikacji FastAPI na serwerze uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
