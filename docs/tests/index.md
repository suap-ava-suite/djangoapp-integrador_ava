# Guia de testes — Integrador AVA

Este documento indexa a documentação de testes do Integrador AVA.
Os testes são todos do tipo unittest (Django `TestCase`) e rodam com PostgreSQL.

Para rodar, use o `ava` CLI do workspace:

```bash
cd ~/projetos/IFRN/ava/workspace
./ava test integrador                # suíte completa do app integrador
./ava test integrador <TestCase>     # apenas um TestCase específico
```

---

## Apps e seus TestCases

| App          | Arquivo de referência       | Principais TestCases                                                    |
|--------------|-----------------------------|-------------------------------------------------------------------------|
| `base`       | [base](base.md)             | `ActiveMixinTestCase`,`BasicModelAdminTestCase`,`BaseModelAdminTestCase`|
| `coorte`     | [coorte](coorte.md)         | `EnrolmentModelTestCase`, `RoleAdminTestCase`, `CohortAdminTestCase`    |
| `health`     | [health](health.md)         | `HealthViewTestCase`, `HealthURLsTestCase`, `HealthMonitoringTestCase`  |
| `integrador` | [integrador](integrador.md) | Ver tabela abaixo                                                       |
| `security`   | [security](security.md)     | `LoginViewTestCase`, `AuthenticateViewTestCase`, `LogoutViewTestCase`   |
| `settings`   | [settings](settings.md)     | `SettingsAppsTestCase`, `SettingsSecuritiesTestCase`                    |

### App `integrador` — TestCases detalhados

| TestCase                         | O que testa                                                                       |
|----------------------------------|-----------------------------------------------------------------------------------|
| `AmbienteModelTestCase`          | Modelo `Ambiente`, `expressao_seletora`, `seleciona_ambiente`                     |
| `SolicitacaoModelTestCase`       | Modelo `Solicitacao`, auto-populate no `save()`, `status_merged`                  |
| `SyncErrorTestCase`              | Classe `SyncError` com código HTTP customizado                                    |
| `UtilsFunctionsTestCase`         | `http_get`, `http_post`,`http_get_json`,`http_post_json`                          |
| `LocalSuapHTTPMockTestCase`      | Mock HTTP do plugin `local_suap`: auth, endpoints, 422, sync_up/down              |
| `ToolSgaHTTPMockTestCase`        | Mock HTTP do plugin `tool_sga`: 400/401/404/501 (stub)                            |
| `AmbienteSelecaoTestCase`        | Seleção de ambiente: múltiplas regras, ordem, sem ambiente, inativo               |
| `CohortSelecaoTestCase`          | Seleção de cohorts via `rule_diario` e `rule_coordenacao`                         |
| `DecoratorsTestCase`             | 8 decorators: `json_response`, `valid_token`, `check_is_post`, etc.               |
| `TrySolicitacaoDecoratorTestCase`| `try_solicitacao`: criação de `Solicitacao`, tratamento de exceções               |
| `MiddlewareTestCase`             | `DisableCSRFForAPIMiddleware` com padrões de URL para isenção                     |
| `BaseBrokerTestCase`             | `BaseBroker`: credentials, `get_cohort`, métodos abstratos                        |
| `Suap2LocalSuapBrokerTestCase`   | Broker `suap2local_suap`: `sync_up_enrolments`, `sync_down_grades`, 422           |
| `ManagementCommandTestCase`      | `atualiza_solicitacoes` (migração de registros antigos)                           |
| `IntegrationTestCase`            | Fluxo completo de `sync_up_enrolments` com todos os decorators                    |
| `EdgeCasesTestCase`              | Múltiplos ambientes, JSON incompleto, expressões complexas                        |

---

## Receitas rápidas (QA)

### 1) Rodar suíte completa

```bash
cd ~/projetos/IFRN/ava/workspace
./ava test integrador
```

### 2) Rodar apenas os testes do mock de Moodle

```bash
./ava test integrador \
    integrador.tests.LocalSuapHTTPMockTestCase \
    integrador.tests.ToolSgaHTTPMockTestCase \
    integrador.tests.Suap2LocalSuapBrokerTestCase
```

### 3) Rodar integração sem Moodle real (forçando mock)

```bash
docker compose run --rm \
    -e MOODLE_HTTP_MOCK_ENABLED=true \
    integrador \
    coverage run manage.py test --verbosity 1 integrador.tests
```

### 4) Subir ambiente para teste de interface com mock em background

No `docker-compose.yml` do workspace, manter no serviço `integrador`:

```yaml
MOODLE_HTTP_MOCK_ENABLED: "true"
MOODLE_HTTP_MOCK_BACKGROUND: "true"
MOODLE_HTTP_MOCK_HOST: "0.0.0.0"
MOODLE_HTTP_MOCK_PORT: "18091"
```

Depois subir normalmente:

```bash
cd ~/projetos/IFRN/ava/workspace
./ava launch integrador
```

### 5) Quando desabilitar o mock

Use Moodle real para validar contrato fim a fim:

```bash
docker compose run --rm \
    -e MOODLE_HTTP_MOCK_ENABLED=false \
    integrador \
    python manage.py test --verbosity 1 integrador.tests.Suap2LocalSuapBrokerTestCase
```

---

## Mock HTTP de Moodle

Para detalhes sobre os mocks HTTP (`LocalSuapHTTPMock`, `ToolSgaHTTPMock`) e como usá-los
em testes de integração sem Moodle real, consulte:

- [moodle_mock](moodle_mock.md)

---

## Cobertura

A política de cobertura exige **mínimo 91%** (meta: 95%).
O gate é aplicado em `pre-push` e no CI.

Para gerar e verificar localmente:

```bash
coverage run --rcfile=src/.coveragerc src/manage.py test --verbosity 1
coverage report --fail-under=91
```
