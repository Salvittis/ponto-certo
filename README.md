# Ficha Técnica — Ponto Certo

| Campo | Definição |
|---|---|
| Produto | **Ponto Certo**, assistente de informação sobre ônibus municipais |
| Cidadão e território | Pessoas que dependem do ônibus municipal no município de São Paulo |
| Problema | Espera longa e dificuldade de obter informação confiável para decidir o deslocamento |
| Proposta de valor | Explicar informações de linhas e espera com evidência, atualização visível e indicação clara de ausência ou falha |
| Arquitetura | Interface web → API FastAPI → recuperação documental e agente de consultas controladas → LLM local; SPTrans como fonte dinâmica quando configurada |
| Fontes | Documentação SPTrans Olho Vivo, portal de desenvolvedores e regras do produto; consultas SPTrans reais no site Azure live, cenários sintéticos identificados no AWS demo; cobertura depende dos retornos da fonte |
| Modelo | Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`, executado localmente com llama.cpp b12464 |
| URLs | Repositório público: [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo). MVP da IA na Azure: [Ponto Certo live](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com), HTTPS, LLM e consultas SPTrans reais validados em 19/11/2026. Cloud temporária na AWS: [Sandbox demo](https://54-210-161-95.sslip.io), checkpoint validado 8b1e298 e inferência real com dados de transporte sintéticos. [Vídeo publicado](https://github.com/Salvittis/ponto-certo/blob/main/evidencias/ponto-certo-demonstracao.mp4). Execução local: `http://127.0.0.1:8000` |
| Indicadores de impacto | Acerto, respostas sem suporte, cobertura e atualidade da informação; posteriormente, compreensão e incerteza percebida pelos cidadãos. Redução da espera não foi medida |
| ODS | **ODS 11**, mobilidade urbana acessível e informação para uso do transporte coletivo; contribuição proposta à [meta 11.2 da ONU](https://sdgs.un.org/goals/goal11), sem alegação de impacto já comprovado |

Projeto da Global Solution CitizenTech 2026.2, Engenharia de Software, 4º ano da FIAP. Responsabilidade de IA e Cloud: Pedro Henrique Salvitti Habiro.

| Integrante | RM |
|---|---|
| Filipe Prado Menezes | RM98765 |
| Cássio Eid Kobaysahi Yonetsuka | RM99678 |
| Pedro Henrique Salvitti Habiro | RM88166 |

Esta entrega usa **a mesma aplicação e o mesmo modelo** nas frentes de IA e Cloud. **Azure mantém a IA pública; AWS Academy Sandbox é o ambiente da entrega Cloud**, conforme aceite do professor relatado por Pedro em 19/11/2026. A Azure está operacionalmente validada. Na AWS, infraestrutura, pipeline, HTTPS, containers, inferência, quatro métricas e ensaio controlado de alerta/recuperação foram comprovados na revisão `8b1e298`, com 15/15 checks do ensaio final aprovados. O documento de entrega está reunido na release pública indicada abaixo. O [guia AWS](docs/CLOUD-AWS.md) e o [estado operacional](docs/STATUS-CLOUD.md) distinguem execução comprovada de preparação. Visão Computacional para lotação, sensor PIR e RPA são componentes previstos pela equipe; não estão implementados nesta frente.

## O que a aplicação faz

A interface permite perguntar em português, consultar linhas e sentidos disponíveis, escolher uma parada retornada e interpretar previsões. Respostas distinguem `ok`, `not_found`, `clarification` e `unavailable`, com fontes e atualização quando aplicáveis. A API usa somente a configuração especializada; as três configurações acadêmicas são comparadas no experimento.

A **Azure está em modo live**, consultando a SPTrans pelo servidor, com credencial protegida e a mesma LLM autohospedada. Na revisão `8b1e298`, os [seis checks públicos](evidencias/cloud/azure-live-public.json) passaram em 19/11/2026 às **11:03:49–11:04:11 de São Paulo**: saúde/prontidão/configuração, ausência honesta de previsão em uma combinação, previsão real em outra e descoberta de quatro opções de linhas. As respostas registraram fonte `SPTRANS_QUERY`, atualização e frescor, sem dados demo. O [deploy live](evidencias/cloud/azure-live-deployment.json) reexecutou somente Azure na tentativa 2 do mesmo run, usando os digests já aprovados; isso não amplia a cobertura observada para toda a cidade.

A **AWS e o modo local padrão permanecem demo**, com dados sintéticos identificados. O cenário usa a linha ilustrativa 8000-10, códigos 1273/34041 e a parada fictícia 4200153. Isso não atesta que a linha atende esse ponto nem sua operação atual. O relógio da simulação é fixo, permitindo reproduzir os casos normal, vazio, desatualizado e indisponível.

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

## Reproduzir com Docker Compose

Esta opção executa a mesma API e a LLM real em containers não root, sem instalar Python ou llama.cpp no host. Requer Docker com Compose e conexão para o primeiro build; os pesos fixados ficam na imagem da LLM. O modo padrão é `demo`, com dados de transporte sintéticos. Não inicie ao mesmo tempo o servidor Python acima na mesma porta.

Na raiz do repositório:

```sh
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml ps
```

Abra `http://127.0.0.1:8000`. A porta padrão é **8000**, publicada somente em loopback; a LLM permanece na rede privada do Compose. Se 8000 estiver ocupada, use `APP_HOST_PORT=8002 docker compose -f compose.yaml up -d --build` e abra `http://127.0.0.1:8002`. Para conferir a integração, com Python 3 disponível no host:

```sh
python3 scripts/smoke.py --base-url http://127.0.0.1:8000 \
  --expect-mode demo --output reports/smoke-compose.json
```

No caso opcional de porta 8002, ajuste também `--base-url`. O smoke verifica saúde, prontidão e respostas reais da LLM; fontes e modo distinguem documento e simulação. Para coletar métricas, defina `METRICS_TOKEN` no `.env` local protegido e ignorado pelo Git, e recrie a app para aplicar a configuração. Use o mesmo token no monitoramento; nunca o publique. `SPTRANS_TOKEN` é necessário somente para `DATA_MODE=live`. Para parar a execução local, use `docker compose -f compose.yaml down`.

## Cloud, pipeline e observabilidade

| Frente | Provedor e continuidade | Estado comprovado |
|---|---|---|
| IA | Azure Students, manutenção planejada até 27/11/2026 às 23h55 de São Paulo | Promoção live comprovada no checkpoint 8b1e298, com [6/6 checks HTTP](evidencias/cloud/azure-live-public.json) e [jornada no navegador](evidencias/jornada-publica-live.json); revisões documentais posteriores da Azure têm SHA próprio |
| Cloud | AWS Academy Sandbox, sessão temporária de 3 horas iniciada em 19/11 às 09:35:56 de São Paulo | Terraform e bootstrap comprovados; revisão 8b1e298 publicada, smoke 5/5, quatro métricas, dois alertas e recuperação. Ensaio final 15/15, primeiro erro contado; PDF final na release pública |

Na AWS, o [apply inicial](evidencias/aws/terraform-applied.json) adicionou 11 recursos. O primeiro bootstrap falhou por ausência do pacote APT `awscli`; a [correção pelo Terraform](evidencias/aws/terraform-replacement.json) substituiu somente a EC2, preservando a rede. A [aplicação AWS](https://54-210-161-95.sslip.io) foi atualizada para `8b1e298a101eb9b90bf723efad268449381e2552`: [pipeline, tentativa 1](evidencias/aws/hardened/pipeline-passed.json) com nove jobs aprovados, [relatórios/deploy](evidencias/aws/hardened/security-passed-summary.json) com 125/125 testes, três imagens sem achados bloqueantes e smoke 5/5. Os [três containers](evidencias/aws/hardened/containers-recovered.json) ficaram saudáveis com UID 10001. O run anterior [44534096169](evidencias/aws/hardened/security-blocked-summary.json) bloqueou publicação e ambos os deploys por CVE-2026-97054 no executável Pebble herdado e não utilizado; ele foi removido, mantendo os scanners ativos, e sua [ausência no runtime AWS](evidencias/aws/hardened/pebble-runtime-verified.json) foi confirmada por SSM. O laboratório apaga recursos e dados ao terminar a sessão; a Azure da IA permanece separada.

O [MVP público](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) está operacional na Azure acadêmica, no Chile. **Histórico da primeira publicação:** em 19/11/2026, o commit `48752d037ee6b7feaee1806ab00dc60e465ad745` concluiu o [run 44521584358](https://github.com/Salvittis/ponto-certo/actions/runs/44521584358): oito jobs e 54 testes aprovados, com deploy e cinco checks HTTPS passando. O [smoke público](evidencias/cloud/smoke-public-first.json) verificou saúde, prontidão, modo demo, resposta documental e chegada demonstrativa com fontes; [saúde/revisão](evidencias/cloud/public-first-ready.json), [contratos de entrada e ausência de informação](evidencias/cloud/public-failure-contracts.json) e [captura da interface](evidencias/cloud/screenshots/public-app.jpg) complementam o checkpoint. Nesse checkpoint histórico, a LLM já era real e autohospedada, com dados de ônibus sintéticos; a promoção live posterior tem evidências próprias. O [estado Cloud](docs/STATUS-CLOUD.md) preserva as falhas anteriores de OIDC/proxy e a consolidação operacional. Os nove checks do [manifesto Azure](evidencias/cloud/manifest.json) estão aprovados; eles não são evidências de execução AWS.

Para reproduzir a infraestrutura **Azure da IA**, siga [infra/OPERACAO.md](infra/OPERACAO.md): conta Azure Students autorizada, crédito/limite de gastos, Terraform, state e `.tfvars` externos, plano revisado, rede somente 80/443 e identidade OIDC. Comece por `bash infra/tf.sh init` e `bash infra/tf.sh validate`; `apply` cria recursos e consome crédito. O [workflow Deploy Blindado](.github/workflows/devsecops.yml) executa build, Gitleaks, Semgrep e Trivy a cada push. Apenas a `main`, por meio do environment `production`, publica os digests aprovados e executa o deploy. [Execuções no GitHub Actions](https://github.com/Salvittis/ponto-certo/actions/workflows/devsecops.yml).

O [Compose de produção](compose.production.yaml) acrescenta Caddy/TLS e mantém app/modelo privados. Imagens GHCR podem exigir autenticação; o código público permite build local. Credenciais pertencem a GitHub Secrets e arquivos protegidos do servidor, nunca a Terraform, imagem ou JavaScript público. A estimativa base é **US$13,45 de crédito educacional por nove dias**, antes de tráfego/operações, com intenção de nenhum desembolso. Manutenção até pelo menos 27/11/2026 às 23h55 de São Paulo, sem desligamento automático.

Para a **AWS Cloud**, [infra/aws](infra/aws/main.tf) mantém conta, state e credenciais separados, com EC2 t2.medium Standard, Ubuntu 24.04, gp2 cifrado de 32 GiB, SSM e entrada somente 80/443. O [deploy AWS](security/AWS-DEPLOY.md) usa o mesmo conjunto de digests aprovados, environment `aws-academy` e credenciais temporárias do Lab; `AWS_ENABLED` habilita somente esse job durante a sessão. Após concluir as provas, a [flag foi definida como false e as três credenciais STS foram removidas do GitHub](evidencias/cloud/live-promotion-config.json), preservando a AWS em demo na revisão validada até o fim do Lab. A tentativa 1 do run `44536511956` passou **125 testes no CI** e os dois deploys, com os mesmos digests aprovados. O [monitor AWS](docs/OBSERVABILIDADE-AWS.md) usa portas locais 9091/3002, projeto, alvos, token e volumes próprios.

Prometheus/Grafana **da Azure** foram validados no computador do operador, monitorando a mesma URL pública da IA. Os containers locais de app/LLM foram parados para liberar memória; o serviço Azure opera independentemente deles. A coleta local exige computador e containers ativos, inclusive após interrupção de energia. Para reproduzir a coleta Azure, com `METRICS_TOKEN` configurado no servidor:

```sh
python3 observability/configure.py \
  --url https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com
docker compose -f compose.monitoring.yaml config --quiet
docker compose -f compose.monitoring.yaml up -d
```

O configurador solicita o token sem exibi-lo. Grafana abre em `http://127.0.0.1:3001/d/ponto-certo-golden-signals` e Prometheus em `http://127.0.0.1:9090`; essas portas ficam locais. Instruções de acesso, consultas, alerta, retenção e coleta sanitizada estão em [OBSERVABILIDADE.md](docs/OBSERVABILIDADE.md). O computador precisa permanecer ativo para coletar. Um dashboard vazio ou uma regra apenas configurada não são evidência de operação.

O ensaio Azure de 19/11/2026 parou e iniciou somente o container LLM, de **12:27:30 a 12:29:31 UTC**. Dois alertas entraram em `firing` às **12:28:51 UTC**; a API continuou viva e a consulta retornou indisponibilidade HTTP 503. A restauração foi confirmada até **12:30:41 UTC**, com prontidão 200, alertas resolvidos e smoke real 5/5. Hash e tamanho dos pesos permaneceram iguais; não houve reboot do host. [Ensaio](evidencias/cloud/alert-exercise.json), [reinício da LLM](evidencias/cloud/restart-public.json), [smoke recuperado](evidencias/cloud/smoke-public-recovered.json), [dashboard](evidencias/cloud/screenshots/dashboard.jpg) e [alerta/recuperação](evidencias/cloud/screenshots/alert-recovered.jpg).

O [ensaio AWS final](evidencias/aws/hardened/alert-exercise.json) passou **15/15 checks** na revisão `8b1e298`. Em 19/11/2026, horário de São Paulo: LLM parada às **10:56:52**, dois alertas firing às **10:58:45**, reinício solicitado às **10:58:52** e recuperação sem alertas ativos às **10:59:47**. A API permaneceu viva e a consulta retornou indisponibilidade/503. O [smoke posterior](evidencias/aws/hardened/smoke-public-recovered.json) passou 5/5; os [três containers](evidencias/aws/hardened/containers-recovered.json) preservaram UID 10001, digests e hash/tamanho do GGUF. O primeiro erro foi medido em [0 antes](evidencias/aws/hardened/first-failure-before.json) e [1 depois](evidencias/aws/hardened/first-failure-after.json), com taxa de **11,1111%/5 min**. A limitação do primeiro ensaio `60aeedd` está corrigida e documentada sem alterar os registros anteriores. [Baseline das quatro métricas](evidencias/aws/hardened/observability-baseline.json), [disparo](evidencias/aws/hardened/observability-firing.json) e [recuperação](evidencias/aws/hardened/observability-recovered.json). Não houve reboot da EC2.

O [documento Cloud](docs/CLOUD.md) apresenta as duas frentes, com [operação AWS](docs/CLOUD-AWS.md) e histórico Azure identificados. Documento de entrega: [Ponto-Certo-Deploy-Blindado.pdf](https://github.com/Salvittis/ponto-certo/releases/download/entrega-cloud-2026-11-19/Ponto-Certo-Deploy-Blindado.pdf), na [release entrega-cloud-2026-11-19](https://github.com/Salvittis/ponto-certo/releases/tag/entrega-cloud-2026-11-19). O PDF reúne arquitetura, evidências, custos e links de reprodução. A publicação do documento não representa submissão acadêmica; o envio fica com Pedro/equipe. O checkpoint das evidências AWS fica fixado em `8b1e298`; revisões documentais posteriores da Azure têm seu próprio SHA. A revisão atual de `/healthz` da Azure pode avançar sem alterar a referência histórica dos testes ou o checkpoint AWS.

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

A integração **local** foi verificada com LLM real para pergunta documental e chegada simulada ([smoke](evidencias/smoke-local.json)); a interface também foi exercitada em desktop e largura de 390 px. [Vídeo demonstrativo local](evidencias/ponto-certo-demonstracao.mp4): quadros de telas reais, com dados de ônibus sintéticos. Os deploys demo passaram seus cinco checks na [tentativa 1 de 8b1e298](evidencias/aws/hardened/security-passed-summary.json). Na promoção Azure live, o [smoke genérico](evidencias/cloud/azure-live-generic-smoke.json) manteve a chegada sem execução (`passed: null`); a [validação pública separada de 6/6 checks](evidencias/cloud/azure-live-public.json) comprovou previsão real, vazio válido e descoberta de linhas com fonte SPTrans e atualização. O [preflight anterior](evidencias/cloud/azure-live-preflight-hardened.json) continua identificado como execução direta do motor. A [jornada pública live pelo navegador](evidencias/jornada-publica-live.json) foi concluída em **19/11/2026 às 11:06:33 de São Paulo**, com identidade/revisão conferida às **11:06:52**: descoberta de quatro opções de linhas, seleção de 14 paradas retornadas e previsão real para a opção escolhida. As cinco capturas, horários e hashes constam do registro; a [tela final](evidencias/interface-publica-live-chegada.jpg) mostra fonte e atualização sem aviso demo. A previsão é observação histórica da consulta, não horário atual nem garantia de chegada.

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
| [Compose local](compose.yaml) / [produção](compose.production.yaml) | Mesma API/LLM em containers; produção inclui proxy HTTPS |
| [Infraestrutura Azure da IA](infra/OPERACAO.md) | Terraform, OIDC, state protegido, custos e manutenção da IA pública |
| [Infraestrutura e operação AWS Cloud](docs/CLOUD-AWS.md) | Sandbox temporário, Terraform/SSM, state separado, reprodução e provas AWS concluídas na revisão 8b1e298, incluindo taxa do primeiro erro |
| [Pipeline DevSecOps](.github/workflows/devsecops.yml) | Build, Gitleaks, Semgrep, Trivy, publicação e deploy com gates |
| [Observabilidade Azure](docs/OBSERVABILIDADE.md) / [AWS](docs/OBSERVABILIDADE-AWS.md) | Quatro métricas, configuração local, alerta e recuperação, com alvos e dados separados |
| [Documento Cloud](docs/CLOUD.md) / [Status Cloud](docs/STATUS-CLOUD.md) | Rubrica, arquitetura, resultados comprovados e pendências |
| [Checkpoint Azure](evidencias/cloud/manifest.json) / [evidências AWS](evidencias/aws/security-passed-summary.json) | Provas identificadas por provedor, URL, horário e revisão; ensaio controlado AWS e recuperação aprovados |

A interface não exige conta, CPF, nome, telefone ou geolocalização. Não informe dados pessoais na pergunta. O aplicativo não mantém histórico de conversas; a operação Cloud deve preservar essa minimização nos logs. Em falha, a interface informa indisponibilidade e permite tentar novamente; o [site da SPTrans](https://www.sptrans.com.br/) é uma alternativa externa.

A Azure está **live** com a LLM autohospedada e seis checks públicos SPTrans aprovados; o histórico de métricas, alerta e recuperação em demo permanece identificado. A AWS Sandbox, aceita pelo professor **conforme relato de Pedro**, permanece **demo na revisão 8b1e298**, com infraestrutura, CI, HTTPS, inferência, runtime, métricas e ensaio final de 15 checks comprovados. O PDF Cloud reúne as evidências do checkpoint AWS e a referência à hospedagem IA na Azure. O envio acadêmico fica com um integrante. O prazo publicado é **19/11/2026 às 23h55**; Pedro/equipe realizam a submissão e conferem a divergência Teams/portal da disciplina Cloud. A preparação técnica não equivale à submissão.
