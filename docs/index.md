# Documentação — Integrador AVA

O **Integrador AVA** é um middleware que conecta Sistemas de Gestão Acadêmica (SGA) ao Moodle.
Suporta o SUAP como padrão principal — pronto de fábrica para o IFRN — e o padrão SGA genérico
para instituições que usam SIGAA, qAcadêmico ou outro sistema acadêmico.

## Como funciona

O Integrador recebe dados de um SGA e os sincroniza com o Moodle. Ele suporta atualmente
**duas convenções de payload** e **três estratégias de integração**, cada uma viabilizada
por um broker próprio.

### Padrões de payload

**Suap** — padrão específico do IFRN, com estrutura de campos bem definida e políticas
institucionais pré-configuradas. Funciona "pronto de fábrica" para quem usa o SUAP.

**SGA** — padrão genérico para qualquer Sistema de Gestão Acadêmica. Mais flexível, porém
requer personalização do middleware por parte da instituição.

## Brokers (estratégias de integração)

|Broker           |Payload recebido|Plugin Moodle|Payload retornado|Customização necessária|Status       |
|-----------------|----------------|-------------|-----------------|-----------------------|-------------|
|`suap2local_suap`|Suap            |`local_suap` |Suap             |Nenhuma                |Implementado |
|`suap2tool_sga`  |Suap            |`tool_sga`   |Suap             |Mínima (config.)       |Em elaboração|
|`sga2tool_sga`   |SGA (genérico)  |`tool_sga`   |Suap             |Requer personalização  |Em elaboração|

### `suap2local_suap` — Suap → plugin `local_suap`

Recebe payload no **padrão Suap**, integra com o plugin Moodle **`local_suap`** e retorna no
**padrão Suap**. Estratégia mais direta, sem necessidade de customização de payload.

|Operação     |Método|URL                   |Descrição                              |
|-------------|------|----------------------|---------------------------------------|
|Enviar diário|POST  |`/api/enviar_diarios/`|Sincroniza matrículas, papéis e coortes|
|Baixar notas |GET   |`/api/baixar_notas/`  |Retorna notas dos alunos do Moodle     |

- **Plugin necessário:** [`local_suap`](https://github.com/cte-zl-ifrn/moodle-local_suap)
- **Referência completa:** [docs/suap2local_suap/](suap2local_suap/index.md)

### `suap2tool_sga` — Suap → plugin `tool_sga`

Recebe payload no **padrão Suap**, traduz para o **padrão SGA** e integra com o plugin
Moodle **`tool_sga`**. Em elaboração.

- **Plugin necessário:** [`tool_sga`](https://github.com/cte-zl-ifrn/moodle-tool_sga)
- **Referência:** [docs/suap2tool_sga/](suap2tool_sga/index.md)

### `sga2tool_sga` — SGA → plugin `tool_sga`

Recebe payload no **padrão SGA genérico** e integra com o plugin Moodle **`tool_sga`**.
Estratégia mais flexível: qualquer SGA pode ser integrado com a personalização adequada.
Em elaboração.

- **Plugin necessário:** [`tool_sga`](https://github.com/cte-zl-ifrn/moodle-tool_sga)
- **Referência:** [docs/sga2tool_sga/](sga2tool_sga/index.md)

## Configuração completa de uma integração

### Passo 1 — Instalar e configurar o plugin no Moodle

|Plugin Moodle|Brokers que o usam             |
|-------------|-------------------------------|
|`local_suap` |`suap2local_suap`              |
|`tool_sga`   |`suap2tool_sga`, `sga2tool_sga`|

Após instalar o plugin no Moodle, configure:

- **Token de autenticação:** valor livre, mas deve ser idêntico ao
  campo `token` do Ambienteno Integrador (Passo 3).
- Demais parâmetros conforme a documentação do respectivo plugin.

### Passo 2 — Configurar as variáveis de ambiente do Integrador

|Variável             |Obrigatória|Descrição                                             |Padrão                    |
|---------------------|-----------|------------------------------------------------------|--------------------------|
|`SUAP_INTEGRADOR_KEY`|Sim        |Token que o SGA deve enviar no header `Authentication`|`changeme`                |
|`DJANGO_SECRET_KEY`  |Sim        |Chave secreta Django (use valor aleatório em produção)|`changeme`                |
|`SUAP_BASE_URL`      |Não        |URL base do SUAP (usada para redirect de logout)      |`https://suap.ifrn.edu.br`|

> **Atenção:** troque `changeme` por valores secretos reais antes de ir para produção.

### Passo 3 — Cadastrar o Ambiente no admin

Acesse `/admin/integrador/ambiente/add/` e cadastre:

|Campo               |Descrição                                                  |Exemplo                     |
|--------------------|-----------------------------------------------------------|----------------------------|
|`nome`              |Nome descritivo                                            |`Moodle Produção ZL`        |
|`url`               |URL base do Moodle (sem barra final)                       |`https://ava.zl.ifrn.edu.br`|
|`token`             |Token configurado no plugin (idêntico ao definido lá)      |`token_secreto_do_plugin`   |
|`expressao_seletora`|Expressão `rule_engine` para seleção automática do ambiente|`campus.sigla == "ZL"`      |
|`ordem`             |Prioridade (menor = maior prioridade)                      |`1`                         |
|`active`            |Se o ambiente está ativo                                   |`true`                      |

> A seleção acontece avaliando `expressao_seletora` de cada ambiente ativo em ordem crescente
> de `ordem`. O primeiro que corresponder ao payload é usado.

Guia completo do admin: [docs/admin/](admin/index.md)

### Passo 4 — Configurar o cliente REST (SGA)

O SGA deve chamar os endpoints com:

- **Header:** `Authentication: Token <SUAP_INTEGRADOR_KEY>`
- **Content-Type** (POST): `application/json`

Exemplo completo para `suap2local_suap`:

```http
POST https://<integrador>/api/enviar_diarios/
Authentication: Token <SUAP_INTEGRADOR_KEY>
Content-Type: application/json

{
    "campus":     {"id": 1,  "sigla": "ZL",      "descricao": "Campus Zona Leste"},
    "curso":      {"id": 1,  "codigo": "15806",  "nome": "Sistemas Operacionais Abertos"},
    "turma":      {"id": 2,  "codigo": "20261.6.15806.1E"},
    "componente": {"id": 1,  "sigla": "TEC.1023","descricao": "Bancos de Dados"},
    "diario":     {"id": 2,  "sigla": "TEC.1023","situacao": "Aberto"}
}
```

```http
GET https://<integrador>/api/baixar_notas/?campus_sigla=ZL&diario_id=2
Authentication: Token <SUAP_INTEGRADOR_KEY>
```

Para exemplos completos de payload, consulte `requests.http` na raiz do projeto.

## Índice da documentação

|Seção                                          |Conteúdo                                                   |
|-----------------------------------------------|-----------------------------------------------------------|
|[Modelos de dados](model/index)                |`Ambiente`, `Solicitacao` — campos, comportamentos, manager|
|[Guia do administrador](admin/index)           |Django admin: Ambientes, Solicitações, Cohorts             |
|[Broker suap2local_suap](suap2local_suap/index)|API completa: endpoints, payload, stack de decorators      |
|[Broker suap2tool_sga](suap2tool_sga/index)    |Em elaboração                                              |
|[Broker sga2tool_sga](sga2tool_sga/index)      |Em elaboração                                              |
|[Guia de testes](tests/index)                  |TestCases, receitas QA, cobertura, mock HTTP               |
|[Mock HTTP de Moodle](tests/moodle_mock)       |`LocalSuapHTTPMock`, `ToolSgaHTTPMock` por broker          |

## Links rápidos

- [Repositório](https://github.com/cte-zl-ifrn/integration-integrador_ava/)
- [README do projeto](https://github.com/cte-zl-ifrn/integration-integrador_ava/)
