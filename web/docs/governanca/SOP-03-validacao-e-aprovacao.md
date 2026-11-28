# SOP-03 — Validação e aprovação de alterações

**Objetivo:** garantir consistência lógica (automática) e correção semântica (humana) antes de qualquer publicação.

**Quem executa:** Engenheiro de Conhecimento (proposição e submissão), raciocinador (verificação), Especialista de Domínio (validação). Stakeholders participam comentando.

## Proposição (Engenheiro)

1. Na solicitação **Em análise**, abrir a **cópia de trabalho no editor** (branch Git `proposta/<id>`).
2. Fazer as alterações no editor 3D, preenchendo os metadados FAIR de cada elemento novo ou alterado.
3. **Salvar rascunho** quantas vezes quiser (cada salvamento é um commit no branch da proposta).
4. **Submeter à verificação**.

## Verificação automática

O sistema executa sobre a cópia de trabalho:

- **Raciocinador HermiT** (OWL 2 DL, cobre SHOIN(D)): consistência lógica e satisfatibilidade das classes;
- **Checagem FAIR**: `rdfs:label`, `rdfs:comment`, `dcterms:source` e `dcterms:creator` em cada elemento novo/alterado;
- **Diff semântico** contra a versão base, com a classificação do impacto (major/minor/patch).

Resultado: **Em validação** (tudo certo) ou **Inconsistente** (volta ao Engenheiro com os problemas listados).

## Validação (Especialista de Domínio)

1. Abrir as propostas **Em validação** (aba Validação).
2. Ler o relatório da verificação e o diff; usar **Revisar no editor** para ver base × proposta com destaque de diferenças.
3. Decidir:
   - **Aprovar** — só se a versão atual da cópia passou na verificação;
   - **Rejeitar** — justificativa obrigatória;
   - **Solicitar ajustes** — descrição obrigatória; a proposta volta ao Engenheiro;
   - **Corrigir triplas** diretamente no editor e salvar — a correção passa de novo pela verificação automática.

## Regras de separação de responsabilidades

- Quem solicitou ou construiu a alteração não aprova a própria proposta.
- Nenhuma alteração gerada automaticamente é publicada sem validação humana.
