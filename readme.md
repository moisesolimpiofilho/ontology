# OntoCube 3D — Guia de Execução e Banco de Dados

Este projeto sobe uma aplicação Flask (OntoCube 3D) juntamente com três bancos de dados (Neo4j, PostgreSQL e MongoDB) utilizando **Docker Compose**. A aplicação recebe arquivos de ontologia (`.owl`, `.rdf`) via upload e persiste os dados estruturados em cada um dos bancos.

## 📋 Pré-requisitos
*   [Docker](https://docs.docker.com/get-docker/) instalado.
*   [Docker Compose](https://docs.docker.com/compose/install/) instalado.

## 🚀 Como iniciar o projeto

1. Abra o terminal na pasta raiz do projeto (onde está o arquivo `docker-compose.yml`).
2. Execute o comando para construir a imagem e subir todos os containers em segundo plano:
   ```bash
   docker compose up -d --build
   ```
3. Verifique se todos os containers estão rodando corretamente:
   ```bash
   docker compose ps
   ```
4. Acesse a aplicação no navegador:
   *   **OntoCube 3D:** [http://localhost:5000](http://localhost:5000)

> **Nota:** Para parar os containers, use `docker compose down`. Para parar e apagar os dados dos bancos, use `docker compose down -v`.

---

## 🔐 Credenciais e Acessos aos Bancos de Dados

Abaixo estão as credenciais configuradas no `docker-compose.yml` para facilitar o acesso local.

### 1. Neo4j (Banco de Grafos)
*   **Interface Web (Neo4j Browser):** [http://localhost:7474](http://localhost:7474)
*   **URL de Conexão (Bolt):** `bolt://localhost:7687`
*   **Usuário:** `neo4j`
*   **Senha:** `senha_forte_neo4j`

### 2. PostgreSQL (Banco Relacional)
*   **Host:** `localhost`
*   **Porta:** `5432`
*   **Usuário:** `admin`
*   **Senha:** `senha_forte_postgres`
*   **Banco de Dados:** `meubanco`

### 3. MongoDB (Banco de Documentos)
*   **Host:** `localhost`
*   **Porta:** `27017`
*   **Usuário:** `admin`
*   **Senha:** `senha_forte_mongo`
*   **Banco de Dados:** `ontocube`
*   **Auth Source:** `admin`

---

## 🔍 Como visualizar os dados após o upload

Após realizar o upload de um arquivo `.owl` na interface web (http://localhost:5000), os dados serão distribuídos nos três bancos. Siga os passos abaixo para visualizá-los:

### 1. Verificando os metadados no PostgreSQL
Você pode usar um cliente SQL (como DBeaver, DataGrip ou pgAdmin) ou acessar via terminal:

```bash
docker exec -it postgres_db psql -U admin -d meubanco
```

Dentro do terminal do Postgres, execute:
```sql
-- Ver o histórico de uploads
SELECT * FROM ontology_uploads ORDER BY uploaded_at DESC;
```
*Para sair, digite `\q`.*

### 2. Visualizando o grafo no Neo4j
Acesse a interface web do Neo4j: [http://localhost:7474](http://localhost:7474).
Use as credenciais (`neo4j` / `senha_forte_neo4j`) e execute as seguintes consultas Cypher:

```cypher
// Ver todas as classes criadas
MATCH (c:Class) RETURN c LIMIT 50;

// Ver as relações de herança (subClassOf)
MATCH (a:Class)-[:SUBCLASS_OF]->(b:Class) RETURN a, b LIMIT 50;

// Ver todos os indivíduos (instâncias)
MATCH (i:Individual) RETURN i LIMIT 50;
```

### 3. Visualizando os documentos no MongoDB
Acesse o terminal do MongoDB usando o comando correto (com `authSource=admin`):

```bash
docker exec -it mongo_db mongosh -u admin -p senha_forte_mongo --authenticationDatabase admin
```

Dentro do shell do Mongo, execute:
```javascript
// Seleciona o banco de dados
use ontocube

// Lista os snapshots salvos (XML bruto + dados parseados)
db.ontology_snapshots.find().pretty()

// Se quiser ver apenas os metadados de um documento específico
db.ontology_snapshots.find({}, {filename: 1, uploaded_at: 1})
```
*Para sair, digite `exit`.*

---
