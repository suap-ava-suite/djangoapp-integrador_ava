# Moodle HTTP Mock

Este documento descreve os mocks HTTP de Moodle da app `integrador`, criados para permitir:

- testes automatizados sem depender de Moodle real com dados;
- desenvolvimento de interface com respostas previsíveis;
- execução local mais estável em modo debug.

Os mocks são implementados em `integrador/moodle_mock.py` e integrados no fluxo HTTP em `integrador/utils.py`.

---

## Visão geral

Existem **3 brokers** no integrador, cada um se comunicando com um plugin Moodle diferente.
Cada broker possui um mock correspondente:

| Broker            | Plugin Moodle | Classe mock         | Endpoint simulado               | Status       |
|-------------------|---------------|---------------------|---------------------------------|--------------|
| `suap2local_suap` | `local_suap`  | `LocalSuapHTTPMock` | `/local/suap/api/index.php`     | Implementado |
| `suap2tool_sga`   | `tool_sga`    | `ToolSgaHTTPMock`   | `/local/tool_sga/api/index.php` | Stub (501)   |
| `sga2tool_sga`    | `tool_sga`    | `ToolSgaHTTPMock`   | `/local/tool_sga/api/index.php` | Stub (501)   |

> **Nota:** `MoodleHTTPMock` é um alias de `LocalSuapHTTPMock` mantido para compatibilidade.
> Prefira usar `LocalSuapHTTPMock` diretamente em código novo.

---

## Broker `suap2local_suap`

**Mock:** `LocalSuapHTTPMock` — simula `/local/suap/api/index.php`
**Classe de teste:** `LocalSuapHTTPMockTestCase`

### Serviços conhecidos

`get_diarios`, `get_atualizacoes_counts`, `set_favourite_course`, `set_visible_course`,
`set_user_preference`, `sync_user_preference`, `sync_up_enrolments`, `sync_down_grades`

### `sync_up_enrolments` (POST)

Valida que o payload contenha os campos obrigatórios:

| Campo        | Subfields obrigatórios              |
|--------------|-------------------------------------|
| `campus`     | `id`, `sigla`, `descricao`          |
| `curso`      | `id`, `codigo`, `nome`              |
| `turma`      | `id`, `codigo`                      |
| `componente` | `id`, `sigla`, `descricao`          |
| `diario`     | `id`, `sigla`, `situacao`           |

Retorno em caso de **sucesso** (espelha o formato real do plugin):

```json
{
    "url":                  "https://<moodle>/course/view.php?id=1",
    "url_sala_coordenacao": "https://<moodle>/course/view.php?id=2",
    "roles_not_found":      []
}
```

Retorno em caso de **payload inválido** (422):

```json
{
    "error": {
        "code":    422,
        "message": "Campos obrigatórios ausentes: campus.id, curso.nome"
    }
}
```

### `sync_down_grades` (GET)

Parâmetro: `?diario_id=<id>`

Retorno:

```json
[
    {
        "matricula": "20260001",
        "nota":       8.5,
        "diario_id":  "123",
        "mock":        true
    }
]
```

### Erros comuns

| Situação                        | HTTP | Corpo                                                        |
|---------------------------------|------|--------------------------------------------------------------|
| Endpoint não reconhecido        | 404  | `{"error": "Endpoint Moodle mock não reconhecido."}`         |
| Serviço desconhecido            | 404  | `{"error": {"code": 404, "message": "Serviço não existe"}}`  |
| Sem cabeçalho `Authentication`  | 400  | `{"error": {"code": 400, "message": "...not informed"}}`     |
| Token incorreto                 | 401  | `{"error": {"code": 401, "message": "Unauthorized"}}`        |
| Serviço não implementado        | 501  | `{"error": {"code": 501, "message": "Não implementado"}}`    |

### Uso em testes

```python
from integrador.moodle_mock import LocalSuapHTTPMock

AUTH = {"Authentication": f"Token {LocalSuapHTTPMock.TOKEN}"}
mock = LocalSuapHTTPMock()

# sync_up_enrolments
payload = {
    "campus":     {"id": 1, "sigla": "ZL",       "descricao": "Campus ZL"},
    "curso":      {"id": 1, "codigo": "15806",   "nome": "Sistemas Operacionais Abertos"},
    "turma":      {"id": 2, "codigo": "20261.6.15806.1E"},
    "componente": {"id": 1, "sigla": "TEC.1023", "descricao": "Bancos de Dados"},
    "diario":     {"id": 2, "sigla": "TEC.1023", "situacao": "Aberto"},
}
response = mock.post(
    "https://moodle.test/local/suap/api/index.php?sync_up_enrolments",
    jsonbody=payload,
    headers=AUTH,
)
assert response.ok
data = json.loads(response.content)
assert "url" in data
assert "roles_not_found" in data

# sync_down_grades
response = mock.get(
    "https://moodle.test/local/suap/api/index.php?sync_down_grades&diario_id=2",
    headers=AUTH,
)
assert response.ok
grades = json.loads(response.content)
assert isinstance(grades, list)
```

### Servidor HTTP em background

O servidor em background é iniciado por `start_mock_moodle_server_in_background()` usando
`LocalSuapHTTPMock`. Ele só está disponível para este broker.

Configure as variáveis em `settings/developments.py`:

| Variável                       | Descrição                                               | Default    |
|--------------------------------|---------------------------------------------------------|------------|
| `MOODLE_HTTP_MOCK_ENABLED`     | `true` → usa mock; `false` → usa `requests` normalmente | `false`    |
| `MOODLE_HTTP_MOCK_BACKGROUND`  | `true` → sobe servidor HTTP em background no DEBUG      | `false`    |
| `MOODLE_HTTP_MOCK_HOST`        | Host de bind do servidor mock                           | `0.0.0.0`  |
| `MOODLE_HTTP_MOCK_PORT`        | Porta do servidor mock                                  | `18091`    |

No `docker-compose.yml` do workspace, o serviço `integrador` já vem pré-configurado com
`MOODLE_HTTP_MOCK_ENABLED=true` e `MOODLE_HTTP_MOCK_BACKGROUND=true`, permitindo validar
fluxos de interface sem provisionar dados no Moodle.

---

## Broker `suap2tool_sga`

**Mock:** `ToolSgaHTTPMock` — simula `/local/tool_sga/api/index.php`
**Classe de teste:** `ToolSgaHTTPMockTestCase`
**Status:** não implementado — retorna 501 para qualquer chamada autenticada.

### Erros esperados

| Situação                        | HTTP |
|---------------------------------|------|
| Endpoint não reconhecido        | 404  |
| Sem cabeçalho `Authentication`  | 400  |
| Token incorreto                 | 401  |
| Qualquer serviço autenticado    | 501  |

### Uso em testes do suap2tool_sga

```python
from integrador.moodle_mock import ToolSgaHTTPMock

AUTH = {"Authentication": f"Token {ToolSgaHTTPMock.TOKEN}"}
mock = ToolSgaHTTPMock()

response = mock.post(
    "https://moodle.test/local/tool_sga/api/index.php?qualquer_servico",
    jsonbody={},
    headers=AUTH,
)
assert response.status_code == 501
```

---

## Broker `sga2tool_sga`

**Mock:** `ToolSgaHTTPMock` — simula `/local/tool_sga/api/index.php`
**Classe de teste:** `ToolSgaHTTPMockTestCase` (compartilhada com `suap2tool_sga`)
**Status:** não implementado — retorna 501 para qualquer chamada autenticada.

Como `suap2tool_sga` e `sga2tool_sga` usam o mesmo plugin Moodle (`tool_sga`) e o mesmo
endpoint, eles compartilham `ToolSgaHTTPMock` e `ToolSgaHTTPMockTestCase`.

Quando esses brokers forem implementados, considere separar as classes de teste por broker
para manter os casos de teste bem delimitados.

---

## Quando usar mock e quando usar Moodle real

Use mock quando:

- o objetivo é validar fluxo da aplicação (UI/API) e regras internas do integrador;
- você precisa de ambiente determinístico para testes repetíveis;
- o Moodle local não está pronto ou sem dados mínimos.

Use Moodle real quando:

- você precisa validar contrato completo de integração;
- quer testar diferenças de payload/erros de plugin real;
- precisa validar comportamento fim a fim em ambiente próximo de produção.

---

## Troubleshooting

- Sintoma: integração continua chamando Moodle real.
  - Verifique `MOODLE_HTTP_MOCK_ENABLED=true`.
  - Confirme se a URL chamada contém o path correto do plugin.

- Sintoma: porta do mock em conflito.
  - Ajuste `MOODLE_HTTP_MOCK_PORT`.

- Sintoma: servidor mock não sobe em background.
  - Verifique se `DJANGO_DEBUG=true`.
  - Verifique `MOODLE_HTTP_MOCK_BACKGROUND=true`.
  - Confira logs da app `integrador`.

---

## Referências de código

| Artefato                  | Caminho                                                                       |
|---------------------------|-------------------------------------------------------------------------------|
| Implementação dos mocks   | `src/integrador/moodle_mock.py`                                               |
| Integração no HTTP client | `src/integrador/utils.py`                                                     |
| Startup em DEBUG          | `src/integrador/apps.py`                                                      |
| Settings de mock          | `src/settings/developments.py`                                                |
| Testes `suap2local_suap`  | `src/integrador/tests.py` → `LocalSuapHTTPMockTestCase`                       |
| Testes `suap2tool_sga`    | `src/integrador/tests.py` → `ToolSgaHTTPMockTestCase`                         |
| Testes `sga2tool_sga`     | `src/integrador/tests.py` → `ToolSgaHTTPMockTestCase`                         |
