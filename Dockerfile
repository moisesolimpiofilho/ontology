FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o requirements.txt que está dentro da pasta web
COPY web/requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia TODO o conteúdo da pasta web (app.py, templates/, static/) para o container
COPY web/ .

# Expõe a porta do Flask
EXPOSE 5000

# Executa o app.py que agora está na raiz do container
CMD ["python", "app.py"]