# WIN-04 — Consultas temporais com CDL

**Usado em:** SOP-04 e auditorias.

A CDL (Change Definition Language) consulta o **Version Log**, que registra por conceito cada alteração declarada e cada inferência materializada, em todas as versões publicadas. Abra **🏛️ Governança → Version Log / CDL**, escolha a ontologia e digite a consulta.

| Consulta | Resultado |
|---|---|
| `VERSIONS` | Versões publicadas, com impacto e responsável. |
| `HISTORY Pessoa` | Todas as mudanças do conceito (nome local ou `<IRI>`). |
| `WHO CHANGED Pessoa` | Quem propôs/aprovou cada mudança do conceito. |
| `STATE Pessoa AT 1.0.0` | Triplas do conceito naquela versão (reconstrução do estado). |
| `CHANGES FROM 1.0.0 TO 2.0.0` | Mudanças publicadas depois da 1.0.0 até a 2.0.0. |
| `CHANGES WHERE impact=major` | Só breaking changes. |
| `CHANGES WHERE kind=inferred AND type=added` | Inferências novas materializadas pelo raciocinador. |
| `CHANGES SINCE 2026-11-01` | Mudanças registradas a partir da data. |

Condições aceitas em `WHERE ... AND ...`: `impact=major|minor|patch`, `type=added|removed|modified`, `kind=asserted|inferred`, `concept=<nome ou IRI>`.
