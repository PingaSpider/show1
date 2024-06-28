# Dockerfile para Dron
FROM python:3.9

WORKDIR /app

COPY Dron/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Dron/AD_Dron.py /app
COPY Nucleo/Mapa.py /app

CMD ["python", "AD_Dron.py"]
