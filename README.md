# Ficha Técnica — Ponto Certo

| Campo | Definição |
|---|---|
| Produto | **Ponto Certo**, assistente de informação sobre ônibus municipais |
| Cidadão e território | Pessoas que dependem do ônibus municipal no município de São Paulo |
| Problema | Espera longa e dificuldade de obter informação confiável para decidir o deslocamento |
| Proposta de valor | Explicar informações de linhas e espera com evidência, atualização visível e indicação clara de ausência ou falha |
| Arquitetura | Interface web → API FastAPI → recuperação documental e agente de consultas controladas → LLM local; SPTrans como fonte dinâmica quando configurada |
| Fontes | Documentação SPTrans Olho Vivo, portal de desenvolvedores, regras do produto e cenários sintéticos versionados; cobertura real da API pendente |
| Modelo | Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`, executado localmente com llama.cpp b12464 |
| URLs | Repositório: [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo), público, arquivos publicados em 19/11/2026. MVP público: **pendente da frente Cloud**. [Vídeo publicado](https://github.com/Salvittis/ponto-certo/blob/main/evidencias/ponto-certo-demonstracao.mp4). Execução local: `http://127.0.0.1:8000` |
| Indicadores de impacto | Acerto, respostas sem suporte, cobertura e atualidade da informação; posteriormente, compreensão e incerteza percebida pelos cidadãos. Redução da espera não foi medida |
| ODS | **ODS 11**, mobilidade urbana acessível e informação para uso do transporte coletivo; contribuição proposta à [meta 11.2 da ONU](https://sdgs.un.org/goals/goal11), sem alegação de impacto já comprovado |

Projeto da Global Solution CitizenTech 2026.2, Engenharia de Software, 4º ano da FIAP. Responsabilidade de IA e Cloud: Pedro Henrique Salvitti Habiro.

| Integrante | RM |
|---|---|
| Filipe Prado Menezes | RM98765 |
| Cássio Eid Kobaysahi Yonetsuka | RM99678 |
| Pedro Henrique Salvitti Habiro | RM88166 |

Esta entrega implementa a frente de Generative AI for Engineering e fornece o contrato para Cloud publicar **esta mesma aplicação**. Visão Computacional para lotação, sensor PIR e RPA são componentes previstos pela equipe; não estão implementados nesta frente.

## O que a aplicação faz

A interface permite perguntar em português, consultar linhas e sentidos disponíveis, escolher uma parada retornada e interpretar previsões. Respostas distinguem `ok`, `not_found`, `clarification` e `unavailable`, com fontes e atualização quando aplicáveis. A API usa somente a configuração especializada; as três configurações acadêmicas são comparadas no experimento.

O modo padrão é **demonstração com dados sintéticos**, autorizada por Pedro enquanto não há token SPTrans disponível. O cenário usa a linha ilustrativa 8000-10, códigos 1273/34041 e a parada fictícia 4200153. Isso não atesta que a linha atende esse ponto nem sua operação atual. O relógio da simulação é fixo, permitindo reproduzir os casos normal, vazio, desatualizado e indisponível. Não é uma consulta ao vivo.

No modo `live`, linhas e paradas vêm da API SPTrans após autenticação. O suporte efetivo depende dos retornos obtidos; nenhuma cobertura integral é prometida. Não há planejador de baldeações, mapa completo de itinerários nem cálculo de trajetos. Uma previsão não garante chegada; uma resposta vazia não comprova ausência de serviço.

## Executar localmente

Requisitos: Python 3.12 (ambiente de reprodução fixado), modelo GGUF e llama.cpp b12464. Downloads iniciais exigem conexão. Os pesos ocupam aproximadamente 1,1 GB; reserve pelo menos 2 GB de disco para os artefatos e, como estimativa inicial, 2–4 GB de RAM para o serviço. A capacidade pública deve ser dimensionada e medida por Cloud.

Na raiz deste repositório:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
mkdir -p .models
curl --fail --location --output .models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

Confira o SHA-256 dos pesos: `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` (1.117.320.736 bytes). Por exemplo, use `shasum -a 256 .models/qwen2.5-1.5b-instruct-q4_k_m.gguf` no macOS ou `sha256sum` no Linux.

Obtenha o binário adequado ao seu sistema na [release b12464 do llama.cpp](https://github.com/ggml-org/llama.cpp/releases/tag/b12464), ou compile essa tag seguindo as instruções oficiais. O modelo tem licença [Apache-2.0](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF); o runtime llama.cpp tem licença MIT. Não substitua o modelo por API comercial para reproduzir o experimento.

Em um terminal, inicie o modelo usando o caminho do seu binário `llama-server`:

```sh
llama-server \
  -m .models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --alias qwen2.5-1.5b-instruct \
  --host 127.0.0.1 --port 8081 \
  -c 4096 -np 1 --metrics
```

Em outro terminal:

```sh
.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --no-access-log
```

Abra `http://127.0.0.1:8000`. O modelo fica na rede privada; apenas a aplicação web deve ser publicada. Para Cloud, procedimentos e responsabilidades estão no [contrato IA–Cloud](docs/CONTRATO-IA-CLOUD.md).

## Configuração e API

`.env.example` é um exemplo sem segredos; `.env` é ignorado pelo Git. `SPTRANS_TOKEN` e `METRICS_TOKEN` são secretos e pertencem somente ao servidor. Não coloque tokens em perguntas, commits, capturas ou comandos publicados. Para consultar a fonte real, configure `SPTRANS_TOKEN` pelo mecanismo de segredos de seu ambiente e `DATA_MODE=live`. O modo demo funciona sem token SPTrans.

| Rota | Uso |
|---|---|
| `GET /` | Interface web |
| `POST /api/ask` | Pergunta e códigos opcionais de linha/ponto/sentido |
| `GET /api/config` | Configuração pública sem credenciais |
| `GET /healthz` | Processo vivo e versão |
| `GET /readyz` | Prontidão das dependências essenciais, distinguindo demo/live |
| `GET /metrics` | Métricas Prometheus, acesso protegido por Bearer |
| `GET /openapi.json` | Esquema exato da API |

Exemplo sem credenciais:

```sh
curl --fail-with-body http://127.0.0.1:8000/api/ask \
  -H 'Content-Type: application/json' \
  --data '{"question":"Previsão garante que o ônibus vai chegar?"}'
```

A resposta informa `status`, `answer`, `sources`, `updated_at`, `data_mode`, `model`, `request_id`, `warnings` e `options`. Entrada inválida retorna HTTP 422; dependência indisponível, HTTP 503. A documentação exata das entradas, variáveis e erros está no contrato.

## Testar e reproduzir a avaliação

Com o servidor do modelo em execução:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m base.evaluate_retrieval
.venv/bin/python -m avaliacao.run --split dev --output avaliacao/runs/dev-repro
.venv/bin/python -m avaliacao.run --split test --output avaliacao/runs/test-repro
```

Escolha diretórios novos em `--output`: o runner preserva evidências e recusa sobrescrever uma execução existente. A recuperação pode ser avaliada sem modelo. Os testes determinísticos e a avaliação com LLM têm propósitos diferentes: os primeiros verificam comportamento de código; a segunda preserva saídas reais do modelo. Veja o [protocolo da avaliação](avaliacao/README.md) antes de executar para conhecer saídas, opções e conjuntos congelados. O experimento compara o mesmo modelo em A: sem contexto, B: RAG simples e C: RAG com agente.

Na recuperação documental, o teste congelado de 14 perguntas respondíveis teve **recall@1 de 92,86% (13/14)** e **recall@3 de 100% (14/14)**; quatro perguntas sem resposta foram rejeitadas. O limiar **0,05** foi escolhido somente no conjunto de desenvolvimento. Estes números vêm de um corpus pequeno e perguntas autorais, não de medição com cidadãos. [Resultados e limites da busca](base/README.md).

O teste final com **24 casos** produziu o seguinte resultado. A revisão semântica foi feita por **um agente**, sem dupla revisão humana, e não representa desempenho populacional.

| Configuração | Acerto por propriedades | Acerto na auditoria semântica | Afirmações finais sem suporte |
|---|---:|---:|---:|
| A — Sem contexto | 9/24 | 9/24 | 2/24 |
| B — RAG simples | 12/24 | 10/24 | 3/24 |
| C — Agente | 15/24 | 15/24 | 0/24 |

O agente melhorou o resultado **do sistema**, mas acertou somente 62,5% dos casos e apresentou recusas excessivas e erros de estado. Houve uma afirmação sem suporte na geração bruta do agente, suprimida antes da resposta final. Foram 17 chamadas à LLM, seis fallbacks extrativos e sete respostas sem chamar o modelo; isso não demonstra aprendizagem dos pesos nem garante ausência geral de alucinação. A presença de fonte também não equivale a suporte semântico. [Placar completo](avaliacao/runs/test-v1/scoreboard.md), [auditoria e cinco erros reais](avaliacao/runs/test-v1/audit.md) e [relatório de IA](docs/RELATORIO-IA.md).

O [notebook executado](notebooks/avaliacao-ia.ipynb) possui seis células de código executadas, 17 saídas salvas e nenhum erro; há também [exportação HTML](notebooks/avaliacao-ia.html). Ele recalcula e apresenta resultados preservados, sem chamar novamente a LLM. Para reproduzi-lo:

```sh
.venv/bin/pip install -r notebooks/requirements.txt
.venv/bin/python notebooks/build_notebook.py --run avaliacao/runs/test-v1
```

A integração **local** foi verificada com LLM real para pergunta documental e chegada simulada ([smoke](evidencias/smoke-local.json)); a interface também foi exercitada em desktop e largura de 390 px. [Vídeo demonstrativo local](evidencias/ponto-certo-demonstracao.mp4): quadros de telas reais, com dados de ônibus sintéticos. A URL pública e a SPTrans ao vivo ainda não foram validadas.

## Artefatos e estado da entrega

| Diretório ou documento | Conteúdo |
|---|---|
| `app/` | API, interface, cliente LLM, recuperação e consultas SPTrans |
| `base/` | Trechos, fontes, manifesto, política e avaliação da recuperação |
| `dados/fixtures/` | Cenários sintéticos versionados, com procedência e relógio fixo |
| `avaliacao/` | Desenvolvimento, teste com gabarito, congelamento e experimento |
| `notebooks/` | [Notebook executado](notebooks/avaliacao-ia.ipynb), [HTML](notebooks/avaliacao-ia.html) e gráfico com saídas salvas |
| [Relatório IA](docs/RELATORIO-IA.md) | Ficha Técnica, arquitetura, fontes, desempenho e limitações |
| [Requisitos](docs/REQUISITOS-IA.md) | Exigências do PDF, escolhas, interpretação e pendências |
| [Contrato IA–Cloud](docs/CONTRATO-IA-CLOUD.md) | Execução, endpoints, segredos, modelo e operação |
| [Status IA](docs/STATUS-IA.md) | Verificações efetivamente executadas e pendências |

A interface não exige conta, CPF, nome, telefone ou geolocalização. Não informe dados pessoais na pergunta. O aplicativo não mantém histórico de conversas; a operação Cloud deve preservar essa minimização nos logs. Em falha, a interface informa indisponibilidade e permite tentar novamente; o [site da SPTrans](https://www.sptrans.com.br/) é uma alternativa externa.

Pendências: integração e URL pública verificadas, consulta SPTrans real e envio acadêmico por um integrante. O prazo publicado é **19/11/2026 às 23h55**; a submissão no Teams fica com Pedro ou o integrante designado. A preparação técnica não equivale à submissão.
