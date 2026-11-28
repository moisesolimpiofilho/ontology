# SOP-02 — Revisão de candidatos gerados pelo Agente LLM

**Objetivo:** transformar candidatos de Ontology Learning em alterações revisadas por humanos, sem que nada gerado automaticamente chegue à versão oficial sem validação.

**Quem executa:** o Engenheiro de Conhecimento dispara a ingestão e revisa; o Agente LLM gera os candidatos e abre a solicitação.

## Execução do agente

1. Abrir **🏛️ Governança → Agente LLM**.
2. Escolher a ontologia, informar a **fonte** (documento, URL, norma) e colar o texto do domínio.
3. Executar. O agente:
   - extrai candidatos a classes, relações e atributos, com definição e evidência;
   - descarta candidatos semelhantes a entidades existentes ou entre si (**filtragem por similaridade vetorial**);
   - anexa as anotações FAIR (`rdfs:label`, `rdfs:comment`, `dcterms:source`, `dcterms:creator = Agente LLM`);
   - abre automaticamente uma solicitação com origem **automática**.

## Revisão

1. Abrir a solicitação criada pelo agente e **Iniciar análise**.
2. **Abrir cópia de trabalho no editor** e usar **Aplicar candidatos no editor** para trazer os candidatos aceitos.
3. Remover ou ajustar no editor os candidatos incorretos; completar metadados FAIR quando necessário.
4. Salvar e submeter (SOP-03 cobre a verificação e a validação).

## Regras

- O agente nunca altera a versão oficial nem aprova/publica.
- Toda proposta do agente passa pelo raciocinador e pela validação do Especialista de Domínio.
- Cada execução fica registrada no MongoDB (`agent_runs`), com modelo, uso de tokens e candidatos descartados.
