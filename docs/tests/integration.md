# Testes de Integração Reais (Docker)

Além dos testes unitários com mocks, este projeto possui uma suíte de **testes de integração reais** que validam o
contrato entre o Integrador AVA e o plugin `local_suap` do Moodle.

Esses testes utilizam contêineres Docker para subir um ambiente completo, incluindo um Moodle real com dados sintéticos.

## Estrutura

- `docker-compose.integration.yml`: Orquestra o Integrador, o Moodle e seus bancos de dados.
- `tests_integration/`: Contém os arquivos de teste (`test_*.py`) e configurações (`conftest.py`).
- `tests_integration/scripts/seed_moodle.php`: Script PHP que popula o Moodle com dados de teste
  (cursos, usuários, notas) usando a API interna do Moodle.

## Como Executar

### 1) Automaticamente (Recomendado)

O comando abaixo sobe todo o ambiente, executa os testes e encerra os contêineres, retornando o código de saída correto:

```bash
docker compose -f docker-compose.integration.yml up --build test-integration --exit-code-from test-integration
```

### 2) Durante o Desenvolvimento

Se você quiser manter o ambiente subido para debugar:

```bash
# Sobe a infra (Moodle + Bancos)
docker compose -f docker-compose.integration.yml up -d moodle db-integrador

# Roda os testes a partir do seu host (requer .venv ativa)
pytest tests_integration --ds=settings -v -s
```

## O que é testado?

Atualmente, os testes cobrem:

1. **`sync_up_enrolments`**:
    - Criação de cursos e categorias.
    - Matrícula de alunos e professores.
    - Sincronização de grupos.
    - Retorno de URLs das salas criadas.

2. **`sync_down_grades`**:
    - Recuperação de notas reais do Gradebook do Moodle.
    - Validação do formato do JSON de notas (incluindo o suporte a PostgreSQL JSONB).

## Pre-push e CI/CD

Estes testes são executados automaticamente:

- Em cada **Push** no GitHub Actions (job `integration`).
- Localmente, se você tiver o `pre-commit` instalado, eles rodam no estágio `pre-push`.

## Troubleshooting

### Moodle não fica pronto

O Moodle pode demorar alguns minutos para inicializar na primeira vez (instalação do banco).
O `docker-compose` está configurado com healthchecks para aguardar, mas se o timeout do
pytest (em `conftest.py`) for atingido, você pode aumentá-lo ou verificar os logs:
`docker compose -f docker-compose.integration.yml logs moodle`
