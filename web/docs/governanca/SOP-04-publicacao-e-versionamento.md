# SOP-04 — Publicação e versionamento

**Objetivo:** incorporar uma alteração aprovada a uma nova versão oficial, rastreável e documentada.

**Quem executa:** Engenheiro de Conhecimento. Só propostas com status **Aprovada** podem ser publicadas.

## Passos

1. Abrir a proposta **Aprovada** e clicar em **Publicar nova versão**.
2. O sistema executa automaticamente:
   1. Classifica o impacto pelo diff semântico e calcula a versão (`major.minor.patch`):
      - **major**: remoção/renomeação de entidade, alteração de domínio/imagem, remoção de axioma, nova restrição em entidade existente;
      - **minor**: novas entidades, propriedades, triplas e axiomas compatíveis;
      - **patch**: apenas rótulos, comentários e metadados.
   2. Preenche os metadados obrigatórios da ontologia: `owl:versionInfo`, `owl:versionIRI`, `owl:priorVersion`, `dcterms:license`.
   3. Faz o merge do branch `proposta/<id>` na `main`, commita a documentação e cria a tag `vX.Y.Z`.
   4. Registra o **Version Log** por conceito (alterações declaradas e inferências materializadas pelo raciocinador).
   5. Gera a documentação da versão (`docs/X.Y.Z.md`).
   6. Atualiza as projeções: snapshot no MongoDB e grafo no Neo4j.
3. Conferir na aba **Ontologias → Versões** a nova versão, a documentação e o arquivo `.owl`.

## Concorrência

Se outra proposta for publicada antes, a versão base fica desatualizada e a publicação é bloqueada. O Engenheiro usa **Reabrir sobre a versão atual**: a cópia antiga é preservada no branch `proposta/<id>-base-<versão>` e a proposta volta para **Em análise**.

## Rastreabilidade

- Versões anteriores ficam disponíveis para consulta e download (tags Git e tabela `ontology_versions`).
- Propostas rejeitadas permanecem no histórico com a justificativa.
- Consultas temporais sobre o histórico: CDL (ver WIN-04).
