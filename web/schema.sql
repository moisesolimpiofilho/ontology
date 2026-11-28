-- Schema da camada de governança (PocGov). Idempotente: executado em todo boot.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT,                 -- NULL para o ator automatizado (não faz login)
    role          TEXT NOT NULL CHECK (role IN ('engenheiro', 'especialista', 'stakeholder', 'agente')),
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cadastro e identificação de ontologias (seção 4.1)
CREATE TABLE IF NOT EXISTS ontologies (
    id              SERIAL PRIMARY KEY,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    iri             TEXT NOT NULL UNIQUE,
    description     TEXT NOT NULL DEFAULT '',
    license         TEXT NOT NULL,      -- dcterms:license (seção 7)
    current_version TEXT,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Versões publicadas (tag Git + conteúdo preservado para consulta e rastreabilidade)
CREATE TABLE IF NOT EXISTS ontology_versions (
    id             SERIAL PRIMARY KEY,
    ontology_id    INTEGER NOT NULL REFERENCES ontologies(id),
    version        TEXT NOT NULL,
    prior_version  TEXT,
    impact         TEXT,                -- major | minor | patch | initial
    git_tag        TEXT,
    git_commit     TEXT,
    proposal_id    INTEGER,
    published_by   INTEGER REFERENCES users(id),
    approved_by    INTEGER REFERENCES users(id),
    published_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content        TEXT NOT NULL,       -- OWL (RDF/XML) publicado
    inferred       JSONB NOT NULL DEFAULT '[]',  -- inferências materializadas pelo raciocinador
    reasoner       JSONB,
    documentation  TEXT,
    UNIQUE (ontology_id, version)
);

-- Solicitações de alteração (issues), inspiradas nas propostas do CRM-SIG (seção 3.1)
CREATE TABLE IF NOT EXISTS proposals (
    id                SERIAL PRIMARY KEY,
    ontology_id       INTEGER NOT NULL REFERENCES ontologies(id),
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    justification     TEXT NOT NULL,
    origin            TEXT NOT NULL CHECK (origin IN ('humana', 'automatica')),
    requester_id      INTEGER NOT NULL REFERENCES users(id),
    affected_elements JSONB NOT NULL DEFAULT '[]',
    source            TEXT NOT NULL DEFAULT '',   -- dcterms:source
    evidence          TEXT NOT NULL DEFAULT '',   -- evidência / definição minerada (LLM)
    candidates        JSONB NOT NULL DEFAULT '[]',
    status            TEXT NOT NULL DEFAULT 'pendente',
    assignee_id       INTEGER REFERENCES users(id),   -- Engenheiro responsável pela alteração
    base_version      TEXT,
    branch            TEXT,
    working_copy      TEXT,
    working_commit    TEXT,
    check_report      JSONB,            -- raciocinador + FAIR
    diff_summary      JSONB,            -- diff semântico em relação à versão base
    impact            TEXT,
    decided_by        INTEGER REFERENCES users(id),
    decision_reason   TEXT,
    decided_at        TIMESTAMPTZ,
    published_version TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS proposals_status_idx ON proposals (ontology_id, status);

-- Deliberação (comentários na issue)
CREATE TABLE IF NOT EXISTS proposal_comments (
    id          SERIAL PRIMARY KEY,
    proposal_id INTEGER NOT NULL REFERENCES proposals(id),
    author_id   INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Histórico de decisões e auditoria (cada transição/ação registrada)
CREATE TABLE IF NOT EXISTS proposal_events (
    id          SERIAL PRIMARY KEY,
    proposal_id INTEGER NOT NULL REFERENCES proposals(id),
    actor_id    INTEGER NOT NULL REFERENCES users(id),
    action      TEXT NOT NULL,
    from_status TEXT,
    to_status   TEXT,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Version Log por conceito (seção 6), incluindo inferências materializadas
CREATE TABLE IF NOT EXISTS version_log (
    id              SERIAL PRIMARY KEY,
    ontology_id     INTEGER NOT NULL REFERENCES ontologies(id),
    version         TEXT NOT NULL,
    concept_iri     TEXT NOT NULL,
    change_type     TEXT NOT NULL CHECK (change_type IN ('added', 'removed', 'modified')),
    kind            TEXT NOT NULL CHECK (kind IN ('asserted', 'inferred')),
    impact          TEXT,
    triples_added   JSONB NOT NULL DEFAULT '[]',
    triples_removed JSONB NOT NULL DEFAULT '[]',
    proposal_id     INTEGER,
    author_id       INTEGER REFERENCES users(id),
    approver_id     INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS version_log_concept_idx ON version_log (ontology_id, concept_iri);
