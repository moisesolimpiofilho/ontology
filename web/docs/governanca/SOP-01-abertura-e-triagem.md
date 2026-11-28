# SOP-01 — Abertura e triagem de solicitações

**Objetivo:** garantir que toda necessidade de mudança na ontologia entre no fluxo de governança como uma solicitação (issue) rastreável.

**Quem executa:** qualquer papel humano (Stakeholder, Engenheiro de Conhecimento, Especialista de Domínio) ou o Agente LLM. A triagem é do Engenheiro de Conhecimento.

## Abertura

1. Entrar no OntoCube 3D e abrir **🏛️ Governança → Solicitações → Nova solicitação**.
2. Selecionar a ontologia afetada.
3. Preencher obrigatoriamente: título, **descrição da necessidade** e **justificativa**.
4. Informar, quando houver: elementos afetados (classes, propriedades, triplas), **fonte do conhecimento** (`dcterms:source`) e evidência.
5. Registrar. A solicitação recebe o status **Pendente**, com solicitante, origem (humana/automática) e data gravados automaticamente.

## Triagem (Engenheiro de Conhecimento)

1. Filtrar as solicitações **Pendentes** da ontologia.
2. Ler a descrição, a justificativa e os comentários (deliberação).
3. Se a solicitação for pertinente: **Iniciar análise** — ela passa a **Em análise**, o Engenheiro vira o responsável e a versão oficial atual é fixada como versão base.
4. Se faltar informação: comentar pedindo complemento ao solicitante.
5. Se não for pertinente: comentar a recomendação; a rejeição formal é do Especialista de Domínio (SOP-03).

## Registros gerados

- Linha em `proposals` e evento `criada` / `iniciar_analise` em `proposal_events` (auditoria).
