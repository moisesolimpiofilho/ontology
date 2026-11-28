# WIN-03 — Tags Git e documentação

**Usado em:** SOP-04.

Cada ontologia tem um repositório Git próprio em `/data/repos/<slug>` (volume `ontology_repos`).

| Ref | Conteúdo |
|---|---|
| `main` | Versão oficial publicada (`ontology.owl`, `docs/`, `VERSION_LOG.md`). |
| `vX.Y.Z` (tag anotada) | Cada versão publicada. |
| `proposta/<id>` | Cópia de trabalho da proposta; cada salvamento é um commit com o autor real. |
| `proposta/<id>-base-<versão>` | Cópia antiga preservada quando a proposta é refeita sobre uma versão mais nova. |

## Consultar

- No painel: **Ontologias → Histórico Git** (commits de todos os branches e tags).
- No terminal:

```bash
docker exec -it flask_app git -C /data/repos/<slug> log --all --oneline --decorate
docker exec -it flask_app git -C /data/repos/<slug> show v1.1.0:ontology.owl
```

## Documentação gerada

A cada publicação é gerado `docs/X.Y.Z.md` com: IRI, versão e versão anterior, tipo de mudança, licença, responsáveis (Engenheiro, Especialista, publicador), tabela de alterações por conceito e o catálogo de classes, relações, atributos e indivíduos com o estado FAIR de cada um. A mesma documentação aparece em **Ontologias → Versões → Documentação**.
