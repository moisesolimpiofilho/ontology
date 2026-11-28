FROM python:3.11-slim

# Sem .pyc gravados (o código é montado do host) e logs sem buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# git: repositório versionado de cada ontologia (branches por proposta, tags por versão)
# Java: executa o raciocinador HermiT (OWL 2 DL, cobre SHOIN(D)) via owlready2
RUN apt-get update \
    && apt-get install -y --no-install-recommends git default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY web/requirements.txt web/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY web/ .

# Pasta onde os .owl enviados são salvos e onde ficam os repositórios Git das ontologias
RUN mkdir -p /app/ontology /data/repos

EXPOSE 5000

CMD ["python", "app.py"]
