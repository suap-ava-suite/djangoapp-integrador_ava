---
trigger: always_on
---

# Regras para Validação de CI e Execução com Act

Para evitar erros recorrentes de CI no GitHub Actions (`static-analysis`, `unit-tests`, `integration-tests`):

1. **Job Names no Act**: O comando `act -j test` falha em repositórios onde os jobs possuem nomes específicos
   (`static-analysis`, `unit-tests`, `integration-tests`).
   - Para validar análise estática e linters (black, markdownlint, doc8):
     `act -j static-analysis`
   - Para validar testes unitários:
     `act -j unit-tests`
   - Para validar testes de integração:
     `act -j integration-tests`
   - Para validar todo o workflow:
     `act` ou `act push`

2. **Obrigatoriedade Local Antes de Qualquer Commit/Push**:
   - Sempre ativar o `.venv` do projeto.
   - Executar obrigatoriamente `pre-commit run --all-files` para garantir formatação, black e markdownlint (MD013 -
     limite 120 caracteres).
   - Executar `pre-commit run --hook-stage pre-push --all-files`.
   - Executar `act -j static-analysis` e `act -j unit-tests` antes de dar push na branch `main`.
