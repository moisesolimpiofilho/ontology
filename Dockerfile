FROM python:3.11-slim

WORKDIR /app

COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web/ .

# Garante a criação da pasta onde os .owl serão salvos
RUN mkdir -p /app/temp

EXPOSE 5000

CMD ["python", "app.py"]