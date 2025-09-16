FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Dipendenze di sistema (OCR + poppler, una sola apt-get)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-ita \
    poppler-utils \
    libgl1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Installazione Python robusta (uvicorn incluso) 
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
# Avvio uvicorn via modulo (no dipendenza da PATH del binario)
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
