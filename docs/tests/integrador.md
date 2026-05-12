# Integrador tests

## Models

- AmbienteModelTestCase: Modelo Ambiente com expressão seletora (Rule), manager customizado, validação de regras,
  propriedade base_url
- SolicitacaoModelTestCase: Modelo Solicitacao com JSON fields, auto-população de campos, choices de Status/Operacao,
  status_merged

## Utils

- SyncErrorTestCase: Classe de erro customizada
- UtilsFunctionsTestCase: http_get, http_post, http_get_json, http_post_json

## Decorators (8 decorators testados)

- DecoratorsTestCase: json_response, exception_as_json, valid_token, check_is_post, check_is_get, check_json,
  detect_ambiente
- TrySolicitacaoDecoratorTestCase: try_solicitacao com sucesso/erro

## Middleware

- MiddlewareTestCase: DisableCSRFForAPIMiddleware com padrões de URL para isenção de CSRF

## Brokers

- BaseBrokerTestCase: Classe base com credentials, get_coortes, métodos abstratos
- Suap2LocalSuapBrokerTestCase: Implementação específica com moodle_base_api_url, sync_up_enrolments, sync_down_grades,
  validação de payload (422)

## Management Commands

- ManagementCommandTestCase: atualiza_solicitacoes para atualizar registros antigos

## Integration & Edge Cases

- IntegrationTestCase: Fluxo completo de sync_up_enrolments com todos os decorators
- EdgeCasesTestCase: Múltiplas regras correspondentes, JSON incompleto, expressões complexas, URLs com barra final

Os testes cobrem todos os aspectos críticos da integração entre SUAP e Moodle, incluindo autenticação via token,
validação de JSON, seleção de ambiente baseada em regras, tratamento de erros, e comunicação HTTP com o AVA.

## Receitas rápidas (QA)

### 1) Rodar suíte completa (fluxo padrão)

No workspace:

```bash
cd ~/projetos/IFRN/ava/workspace
./ava test integrador
```

### 2) Rodar apenas os testes do mock de Moodle

```bash
cd ~/projetos/IFRN/ava/workspace
./ava test integrador \
 integrador.tests.LocalSuapHTTPMockTestCase \
 integrador.tests.ToolSgaHTTPMockTestCase \
 integrador.tests.Suap2LocalSuapBrokerTestCase
```

### 3) Rodar integração sem Moodle real (forçando mock)

Quando quiser garantir execução sem dependência externa:

```bash
cd ~/projetos/IFRN/ava/workspace
docker compose run --rm \
 -e MOODLE_HTTP_MOCK_ENABLED=true \
 integrador \
 coverage run manage.py test --verbosity 1 integrador.tests
```

### 4) Subir ambiente para teste de interface com mock em background

No `docker-compose.yml` do workspace, manter no serviço `integrador`:

- `MOODLE_HTTP_MOCK_ENABLED=true`
- `MOODLE_HTTP_MOCK_BACKGROUND=true`
- `MOODLE_HTTP_MOCK_HOST=0.0.0.0`
- `MOODLE_HTTP_MOCK_PORT=18091`

Depois subir normalmente:

```bash
cd ~/projetos/IFRN/ava/workspace
./ava launch integrador
```

Assim, chamadas para `/local/suap/api/index.php` são atendidas pelo mock, facilitando teste de tela e fluxo sem carga
de dados no Moodle.

### 5) Quando desabilitar o mock

Use Moodle real para validar contrato fim a fim:

```bash
cd ~/projetos/IFRN/ava/workspace
docker compose run --rm \
 -e MOODLE_HTTP_MOCK_ENABLED=false \
 integrador \
 python manage.py test --verbosity 1 integrador.tests.Suap2LocalSuapBrokerTestCase
```

### Referência

Detalhes completos de arquitetura e troubleshooting do mock em:

- [moodle_mock](moodle_mock.md)
