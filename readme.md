# OntoCube 3D — Guia de Execução, Governança e Banco de Dados

Editor e visualizador 3D de ontologias OWL/RDF com uma **camada de governança** (modelo PocGov): papéis e permissões, solicitações de alteração (issues), verificação automática com raciocinador OWL DL e metadados FAIR, validação humana, publicação com versionamento semântico em Git, Version Log com consultas temporais (CDL) e um Agente LLM de Ontology Learning.

Sobe com **Docker Compose**: aplicação Flask + Neo4j + PostgreSQL + MongoDB.

## 📋 Pré-requisitos
*   [Docker](https://docs.docker.com/get-docker/) com o plugin [Docker Compose](https://docs.docker.com/compose/install/) (no Ubuntu/WSL: `sudo apt install docker-compose-v2`).

## 🚀 Como iniciar o projeto

1. Na pasta raiz do projeto (onde está o `docker-compose.yml`):
   ```bash
   docker compose up -d --build
   ```
2. Confira os containers (os três bancos devem ficar `healthy`):
   ```bash
   docker compose ps
   ```
3. Acesse **[http://localhost:5000](http://localhost:5000)**.

> Para parar: `docker compose down`. Para parar **e apagar todos os dados** (bancos e repositórios Git das ontologias): `docker compose down -v`.

## 👤 Login opcional e papéis

*   **Sem login (modo visitante):** a tela inicial e o editor 3D funcionam por completo — carregar `.owl`, criar e editar classes, relações e objetos, validar e exportar. **Nada é salvo no servidor** e, ao recarregar a página (F5), tudo é perdido.
*   **Com login:** o painel **🏛️ Governança** libera as funções de acordo com o papel:

| Papel | Pode |
|---|---|
| Engenheiro de Conhecimento | Cadastrar ontologias, analisar solicitações, editar a cópia de trabalho, submeter à verificação, publicar versões, disparar o Agente LLM. |
| Especialista de Domínio | Validar, aprovar, rejeitar, solicitar ajustes e corrigir triplas durante a validação. |
| Stakeholder | Consultar ontologias e versões, registrar solicitações, comentar. |
| Agente LLM (automático) | Gerar candidatos e abrir solicitações; nunca aprova nem publica. |

No primeiro boot (banco sem usuários) são criadas três contas de demonstração: `engenheiro`, `especialista` e `stakeholder`, todas com a senha definida em `SEED_PASSWORD` (veja `.env.example`). O autocadastro na tela de login cria contas de **Stakeholder**. Para criar contas com outros papéis:

```bash
docker exec -it flask_app flask --app app create-user maria especialista --name "Maria Silva"
```

## 🏛️ Fluxo de governança

1. **Solicitação** (qualquer papel): fica *Pendente*.
2. **Análise** (Engenheiro): *Em análise*; a versão oficial vira a base e a cópia de trabalho fica no branch Git `proposta/<id>`. O Engenheiro abre a cópia no editor 3D, edita e salva (cada salvamento é um commit).
3. **Verificação automática** ao submeter: raciocinador **HermiT** (OWL 2 DL, cobre SHOIN(D)), metadados **FAIR** (`rdfs:label`, `rdfs:comment`, `dcterms:source`, `dcterms:creator`) nos elementos novos/alterados e **diff semântico** com o impacto (major/minor/patch). Resultado: *Em validação* ou *Inconsistente*.
4. **Validação** (Especialista): revisa no editor com o diff destacado e aprova, rejeita (com justificativa) ou solicita ajustes. Quem pediu ou construiu a alteração não aprova a própria proposta.
5. **Publicação** (Engenheiro, só com status *Aprovada*): calcula a versão, preenche `owl:versionInfo`, `owl:versionIRI`, `owl:priorVersion` e `dcterms:license`, faz merge + tag `vX.Y.Z`, registra o Version Log (inclusive as inferências materializadas), gera a documentação e atualiza Mongo e Neo4j.

Os procedimentos operacionais (SOP-01 a 04) e as instruções de trabalho (WIN-01 a 04) estão em [`web/docs/governanca/`](web/docs/governanca/) e na aba **Procedimentos** do painel.

## ⚙️ Configuração

Copie `.env.example` para `.env` para trocar os padrões de desenvolvimento (o `.env` é ignorado pelo git).

| Variável | Para quê |
|---|---|
| `SECRET_KEY` | Assina o cookie de sessão do login. |
| `SEED_PASSWORD` | Senha das contas de demonstração criadas no primeiro boot. |
| `ANTHROPIC_API_KEY` | Liga o Agente LLM (Claude). Vazia: o agente fica desativado e o resto funciona. |
| `LLM_MODEL` / `LLM_EFFORT` | Modelo (padrão `claude-opus-5-5`) e esforço do agente. |
| `REASONER_TIMEOUT` | Tempo máximo do HermiT por verificação (padrão 120 s). |
| `NEO4J_PASSWORD`, `POSTGRES_PASSWORD`, `MONGO_PASSWORD` | Senhas dos bancos. |
| `FLASK_DEBUG` | `1` (padrão) liga o hot reload; o código de `web/` é montado no container. |
| `MAX_UPLOAD_MB` | Limite das requisições (padrão 10 MB). |

Todas as portas são publicadas apenas em `127.0.0.1`.

## 🔌 API (resumo)

Requisições que alteram estado exigem o cabeçalho `X-OntoCube: 1` (proteção contra CSRF) e sessão de login.

| Rota | Descrição |
|---|---|
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/register` | Login opcional. |
| `GET/POST /api/ontologies` | Listar / cadastrar ontologia (versão inicial 1.0.0). |
| `GET /api/ontologies/<id>/versions/<v>[?format=owl]` | Versão publicada, documentação, download. |
| `GET /api/ontologies/<id>/git-log`, `/graph`, `/version-log` | Histórico Git, grafo no Neo4j, Version Log. |
| `POST /api/ontologies/<id>/cdl` | Consulta temporal CDL (`HISTORY`, `STATE ... AT`, `CHANGES ...`). |
| `GET/POST /api/proposals`, `GET /api/proposals/<id>` | Solicitações. |
| `POST /api/proposals/<id>/working-copy` | Salvar a cópia de trabalho (e opcionalmente submeter). |
| `POST /api/proposals/<id>/actions/<ação>` | `iniciar_analise`, `submeter`, `aprovar`, `rejeitar`, `solicitar_ajustes`, `publicar`, `reabrir_base_atual`. |
| `POST /api/agent/run` | Executa o Agente LLM e abre a solicitação com os candidatos. |

## 🧪 Testes

```bash
# testes unitários (regras, diff semântico, CDL, FAIR, agente com cliente simulado, HermiT real)
docker exec flask_app sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests -q"

# fluxo ponta a ponta contra a API em execução (cria dados de teste)
docker exec flask_app python tests/e2e_governance.py
```

---

## 🔐 Acesso aos bancos de dados

Credenciais padrão do `docker-compose.yml` (troque pelo `.env`).

| Banco | Acesso | Usuário / senha | Base |
|---|---|---|---|
| Neo4j | [http://localhost:7474](http://localhost:7474), `bolt://localhost:7687` | `neo4j` / `senha_forte_neo4j` | — |
| PostgreSQL | `localhost:5432` | `admin` / `senha_forte_postgres` | `meubanco` |
| MongoDB | `localhost:27017` (authSource `admin`) | `admin` / `senha_forte_mongo` | `ontocube` |

### O que fica em cada lugar

*   **PostgreSQL** (fonte da verdade): `users`, `ontologies`, `ontology_versions` (conteúdo de cada versão), `proposals`, `proposal_comments`, `proposal_events` (auditoria), `version_log`.
    ```bash
    docker exec -it postgres_db psql -U admin -d meubanco -c "SELECT id, title, status FROM proposals ORDER BY id;"
    ```
*   **Git** (fonte da verdade do conteúdo): um repositório por ontologia em `/data/repos/<slug>` (volume `ontology_repos`).
    ```bash
    docker exec -it flask_app git -C /data/repos/<slug> log --all --oneline --decorate
    ```
*   **MongoDB** (projeção): `ontology_snapshots` (cada versão publicada) e `agent_runs` (execuções do Agente LLM).
    ```bash
    docker exec -it mongo_db mongosh -u admin -p senha_forte_mongo --authenticationDatabase admin ontocube --eval "db.ontology_snapshots.find({}, {version:1, ontology_iri:1})"
    ```
*   **Neo4j** (projeção): grafo da versão publicada de cada ontologia.
    ```cypher
    MATCH (c:Class) WHERE 'http://xmlns.com/foaf/0.1/' IN c.ontologies RETURN c LIMIT 50;
    MATCH (a:Class)-[:SUBCLASS_OF]->(b:Class) RETURN a, b LIMIT 50;
    ```
