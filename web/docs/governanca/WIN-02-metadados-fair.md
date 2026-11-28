# WIN-02 — Preenchimento dos metadados FAIR

**Usado em:** SOP-02, SOP-03.

## Por elemento (classe, propriedade ou indivíduo)

| Campo no inspetor | Propriedade | O que colocar |
|---|---|---|
| Rótulo | `rdfs:label` | Nome legível. |
| Descrição | `rdfs:comment` | Definição textual de uma ou duas frases. |
| Fonte | `dcterms:source` | Documento, norma ou URL que sustenta a definição. |
| Criador / origem | `dcterms:creator` | Preenchido com o seu nome ao criar; `Agente LLM (OntoCube)` para candidatos automáticos. |

1. Selecione o elemento no Explorador ou no palco 3D.
2. No **Inspetor**, preencha os quatro campos e clique em **Salvar**. O indicador **FAIR x/4** mostra o que falta.
3. Elementos novos ou alterados sem os quatro campos tornam a proposta **Inconsistente** na verificação automática. Elementos antigos (não alterados) sem metadados aparecem apenas como aviso.

## Da ontologia

`owl:versionInfo`, `owl:versionIRI`, `owl:priorVersion` e `dcterms:license` são preenchidos automaticamente na publicação, a partir da versão calculada e da licença cadastrada (padrão **CC BY 4.0**).
