# WIN-01 — Execução do raciocinador

**Usado em:** SOP-03.

1. A verificação roda ao **Submeter à verificação** (Engenheiro) e a cada **correção salva** pelo Especialista.
2. Tecnicamente: o backend grava a cópia de trabalho num arquivo temporário e executa `python -m services.reasoner_worker` num processo separado, com o HermiT (via owlready2 + Java).
   - `owl:imports` são removidos antes, para não buscar ontologias na rede.
   - Tempo máximo: `REASONER_TIMEOUT` (padrão 120 s). Memória do Java: `REASONER_JAVA_MEMORY` (padrão 768 MB).
3. Leitura do resultado (painel da proposta → *Verificação automática*):
   - **consistent**: a ontologia é consistente; confira a lista de classes insatisfatíveis (deve estar vazia).
   - **inconsistent**: há contradição lógica (ex.: indivíduo membro de duas classes disjuntas).
   - **error**: o HermiT não conseguiu processar (ex.: construção fora do OWL 2 DL). Trate como inconsistência.
4. As **inferências** listadas (subclasses, equivalências, tipos inferidos) são materializadas no Version Log na publicação.
5. Para reproduzir manualmente dentro do container:

```bash
docker exec -it flask_app python -m services.reasoner_worker /caminho/ontologia.owl
```
