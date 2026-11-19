# Ficha Técnica — Ponto Certo

| Campo | Definição |
|---|---|
| Produto | **Ponto Certo**, assistente de informação sobre ônibus municipais |
| Cidadão e território | Pessoas que dependem do ônibus municipal no município de São Paulo |
| Problema | Espera longa e dificuldade de obter informação confiável para decidir o deslocamento |
| Proposta de valor | Explicar informações de linhas e espera com evidência, atualização visível e indicação clara de ausência ou falha |
| Arquitetura | Interface web → API FastAPI → recuperação documental e agente de consultas controladas → LLM local; SPTrans como fonte dinâmica quando configurada |
| Fontes | Documentação SPTrans Olho Vivo, portal de desenvolvedores, regras do produto e cenários sintéticos versionados; consulta real SPTrans/LLM passou em preflight restrito, sem cobertura integral nem site live declarado |
| Modelo | Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`, executado localmente com llama.cpp b12464 |
| URLs | Repositório: [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo), público, arquivos publicados em 19/11/2026. MVP público da IA na Azure: [Ponto Certo](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com), HTTPS e inferência validados em 19/11/2026, modo demo. Cloud temporária na AWS: [Sandbox](https://54-210-161-95.sslip.io), publicação e inferência comprovadas na sessão de 19/11. [Vídeo publicado](https://github.com/Salvittis/ponto-certo/blob/main/evidencias/ponto-certo-demonstracao.mp4). Execução local: `http://127.0.0.1:8000` |
| Indicadores de impacto | Acerto, respostas sem suporte, cobertura e atualidade da informação; posteriormente, compreensão e incerteza percebida pelos cidadãos. Redução da espera não foi medida |
| ODS | **ODS 11**, mobilidade urbana acessível e informação para uso do transporte coletivo; contribuição proposta à [meta 11.2 da ONU](https://sdgs.un.org/goals/goal11), sem alegação de impacto já comprovado |

Projeto da Global Solution CitizenTech 2026.2, Engenharia de Software, 4º ano da FIAP. Responsabilidade de IA e Cloud: Pedro Henrique Salvitti Habiro.

| Integrante | RM |
|---|---|
| Filipe Prado Menezes | RM98765 |
| Cássio Eid Kobaysahi Yonetsuka | RM99678 |
| Pedro Henrique Salvitti Habiro | RM88166 |

Esta entrega usa **a mesma aplicação e o mesmo modelo** nas frentes de IA e Cloud. **Azure mantém a IA pública; AWS Academy Sandbox é o ambiente da entrega Cloud**, conforme aceite do professor relatado por Pedro em 19/11/2026. A Azure está operacionalmente validada. Na AWS, infraestrutura, pipeline, HTTPS, containers, inferência, quatro métricas e ensaio controlado de alerta/recuperação foram comprovados na revisão `60aeedd`. A consolidação e revisão visual do PDF final ainda estão pendentes. O [guia AWS](docs/CLOUD-AWS.md) e o [estado operacional](docs/STATUS-CLOUD.md) distinguem execução comprovada de preparação. Visão Computacional para lotação, sensor PIR e RPA são componentes previstos pela equipe; não estão implementados nesta frente.

## O que a aplicação faz

A interface permite perguntar em português, consultar linhas e sentidos disponíveis, escolher uma parada retornada e interpretar previsões. Respostas distinguem `ok`, `not_found`, `clarification` e `unavailable`, com fontes e atualização quando aplicáveis. A API usa somente a configuração especializada; as três configurações acadêmicas são comparadas no experimento.

O modo padrão e as duas publicações deste checkpoint são **demonstração com dados sintéticos**, autorizada por Pedro. A credencial SPTrans já foi obtida de forma protegida e um [preflight restrito na Azure](evidencias/cloud/azure-live-preflight.json) comprovou consulta real com a LLM; o serviço público continua demo até concluir o hardening de frescor/coerência da resposta SPTrans, repetir o preflight e validar o modo live por HTTP. O cenário usa a linha ilustrativa 8000-10, códigos 1273/34041 e a parada fictícia 4200153. Isso não atesta que a linha atende esse ponto nem sua operação atual. O relógio da simulação é fixo, permitindo reproduzir os casos normal, vazio, desatualizado e indisponível. Não é uma consulta ao vivo.

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
| IA | Azure Students, manutenção planejada até 27/11/2026 às 23h55 de São Paulo | HTTPS, inferência, alerta e recuperação aprovados; [checkpoint 60aeedd](https://github.com/Salvittis/ponto-certo/actions/runs/44528188191) publicado em modo demo; preflight SPTrans real restrito aprovado, publicação live ainda pendente |
| Cloud | AWS Academy Sandbox, sessão temporária de 3 horas iniciada em 19/11 às 09:35:56 de São Paulo | Terraform e bootstrap comprovados; pipeline de nove jobs aprovado, smoke HTTPS 5/5 e inferência pública real. Quatro métricas, dois alertas disparados e recuperação aprovados; PDF final ainda pendente |

Na AWS, o [apply inicial](evidencias/aws/terraform-applied.json) adicionou 11 recursos. O primeiro bootstrap falhou por ausência do pacote APT `awscli`; a [correção pelo Terraform](evidencias/aws/terraform-replacement.json) substituiu somente a EC2: 1 adição, 0 alterações e 1 destruição, preservando a rede. A [aplicação AWS](https://54-210-161-95.sslip.io) foi publicada na revisão `60aeeddc0509cf6c82c65485f67fae67ad494a62`: [pipeline](evidencias/aws/pipeline-passed.json) com nove jobs aprovados, [relatórios/deploy](evidencias/aws/security-passed-summary.json) com 78/78 testes e smoke 5/5, [TLS e rede](evidencias/aws/public-network.json) e [três containers não root](evidencias/aws/containers-baseline.json) comprovados. A [série pública](evidencias/aws/public-observation-traffic.json) passou 12/12 perguntas entre 13:16:12 e 13:17:50 UTC, em 7,180–8,996 s por chamada; é uma demonstração sequencial, não benchmark de capacidade. O laboratório apaga recursos e dados ao terminar a sessão. Antes do encerramento, serão preservadas as evidências próprias da AWS no documento Cloud; a Azure da IA permanece separada.

O [MVP público](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) está operacional na Azure acadêmica, no Chile. Em 19/11/2026, o commit `48752d037ee6b7feaee1806ab00dc60e465ad745` concluiu o [run 44521584358](https://github.com/Salvittis/ponto-certo/actions/runs/44521584358): oito jobs e 54 testes aprovados, com deploy e cinco checks HTTPS passando. O [smoke público](evidencias/cloud/smoke-public-first.json) verificou saúde, prontidão, modo demo, resposta documental e chegada demonstrativa com fontes; [saúde/revisão](evidencias/cloud/public-first-ready.json), [contratos de entrada e ausência de informação](evidencias/cloud/public-failure-contracts.json) e [captura da interface](evidencias/cloud/screenshots/public-app.jpg) complementam o checkpoint. A LLM é real e autohospedada; os dados de ônibus continuam sintéticos. O [estado Cloud](docs/STATUS-CLOUD.md) preserva as falhas anteriores de OIDC/proxy e a consolidação operacional. Os nove checks do [manifesto Azure](evidencias/cloud/manifest.json) estão aprovados; eles não são evidências de execução AWS.

Para reproduzir a infraestrutura **Azure da IA**, siga [infra/OPERACAO.md](infra/OPERACAO.md): conta Azure Students autorizada, crédito/limite de gastos, Terraform, state e `.tfvars` externos, plano revisado, rede somente 80/443 e identidade OIDC. Comece por `bash infra/tf.sh init` e `bash infra/tf.sh validate`; `apply` cria recursos e consome crédito. O [workflow Deploy Blindado](.github/workflows/devsecops.yml) executa build, Gitleaks, Semgrep e Trivy a cada push. Apenas a `main`, por meio do environment `production`, publica os digests aprovados e executa o deploy. [Execuções no GitHub Actions](https://github.com/Salvittis/ponto-certo/actions/workflows/devsecops.yml).

O [Compose de produção](compose.production.yaml) acrescenta Caddy/TLS e mantém app/modelo privados. Imagens GHCR podem exigir autenticação; o código público permite build local. Credenciais pertencem a GitHub Secrets e arquivos protegidos do servidor, nunca a Terraform, imagem ou JavaScript público. A estimativa base é **US$13,45 de crédito educacional por nove dias**, antes de tráfego/operações, com intenção de nenhum desembolso. Manutenção até pelo menos 27/11/2026 às 23h55 de São Paulo, sem desligamento automático.

Para a **AWS Cloud**, [infra/aws](infra/aws/main.tf) mantém conta, state e credenciais separados, com EC2 t2.medium Standard, Ubuntu 24.04, gp2 cifrado de 32 GiB, SSM e entrada somente 80/443. O [deploy AWS](security/AWS-DEPLOY.md) usa o mesmo conjunto de digests aprovados, environment `aws-academy` e credenciais temporárias do Lab; `AWS_ENABLED` habilita somente esse job durante a sessão. O run publicado passou **78 testes no CI** e os dois deploys; alterações posteriores ainda precisam de nova execução aprovada do pipeline. O [monitor AWS](docs/OBSERVABILIDADE-AWS.md) usa portas locais 9091/3002, projeto, alvos, token e volumes próprios.

Prometheus/Grafana **da Azure** foram validados no computador do operador, monitorando a mesma URL pública da IA. Os containers locais de app/LLM foram parados para liberar memória; o serviço Azure opera independentemente deles. A coleta local exige computador e containers ativos, inclusive após interrupção de energia. Para reproduzir a coleta Azure, com `METRICS_TOKEN` configurado no servidor:

```sh
python3 observability/configure.py \
  --url https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com
docker compose -f compose.monitoring.yaml config --quiet
docker compose -f compose.monitoring.yaml up -d
```

O configurador solicita o token sem exibi-lo. Grafana abre em `http://127.0.0.1:3001/d/ponto-certo-golden-signals` e Prometheus em `http://127.0.0.1:9090`; essas portas ficam locais. Instruções de acesso, consultas, alerta, retenção e coleta sanitizada estão em [OBSERVABILIDADE.md](docs/OBSERVABILIDADE.md). O computador precisa permanecer ativo para coletar. Um dashboard vazio ou uma regra apenas configurada não são evidência de operação.

O ensaio Azure de 19/11/2026 parou e iniciou somente o container LLM, de **12:27:30 a 12:29:31 UTC**. Dois alertas entraram em `firing` às **12:28:51 UTC**; a API continuou viva e a consulta retornou indisponibilidade HTTP 503. A restauração foi confirmada até **12:30:41 UTC**, com prontidão 200, alertas resolvidos e smoke real 5/5. Hash e tamanho dos pesos permaneceram iguais; não houve reboot do host. [Ensaio](evidencias/cloud/alert-exercise.json), [reinício da LLM](evidencias/cloud/restart-public.json), [smoke recuperado](evidencias/cloud/smoke-public-recovered.json), [dashboard](evidencias/cloud/screenshots/dashboard.jpg) e [alerta/recuperação](evidencias/cloud/screenshots/alert-recovered.jpg).

O [ensaio AWS](evidencias/aws/alert-exercise.json) passou **12/12 checks** na revisão `60aeedd`: a LLM foi parada às **10:21:35** de São Paulo e reiniciada às **10:23:36**; dois alertas estavam em firing às **10:22:57**, e a recuperação sem alertas ativos foi confirmada às **10:24:28**. Durante a falha, a API permaneceu viva e a consulta respondeu indisponibilidade/503. O [smoke posterior](evidencias/aws/smoke-public-recovered.json) passou 5/5; os [três containers recuperados](evidencias/aws/containers-recovered.json) mantiveram UID 10001, digests e hash/tamanho dos pesos. Não houve reboot da EC2. [Baseline das quatro métricas](evidencias/aws/observability-baseline.json), [alerta disparado](evidencias/aws/screenshots/alerts-firing.jpg) e [recuperação](evidencias/aws/screenshots/dashboard-recovered.jpg).

O [documento Cloud](docs/CLOUD.md) apresenta as duas frentes, com [operação AWS](docs/CLOUD-AWS.md) e histórico Azure identificados. A antiga decisão de evitar o Sandbox por sua duração foi revista após a orientação relatada por Pedro; suas restrições continuam relevantes. **O PDF final Cloud aguarda consolidação das evidências já comprovadas, geração e revisão visual**, com provedor, URL, revisão e janela próprios. O [gerador](scripts/build-cloud-pdf.py) aceita manifesto AWS separado; a entrega final passará por renderização e revisão visual. Preservar as provas antes do fim do Sandbox não encerra a Azure da IA.

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

A integração **local** foi verificada com LLM real para pergunta documental e chegada simulada ([smoke](evidencias/smoke-local.json)); a interface também foi exercitada em desktop e largura de 390 px. [Vídeo demonstrativo local](evidencias/ponto-certo-demonstracao.mp4): quadros de telas reais, com dados de ônibus sintéticos. A integração pública também passou os cinco checks HTTPS do [smoke Cloud](evidencias/cloud/smoke-public-first.json), com o mesmo modelo e dados demo. O [preflight SPTrans/LLM na Azure](evidencias/cloud/azure-live-preflight.json) passou para uma combinação real de linha/parada/sentido; esse teste direto do motor não comprova ainda o site público em live nem cobertura geral.

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
| [Infraestrutura e operação AWS Cloud](docs/CLOUD-AWS.md) | Sandbox temporário, Terraform/SSM, state separado, reprodução e provas AWS concluídas na revisão 60aeedd |
| [Pipeline DevSecOps](.github/workflows/devsecops.yml) | Build, Gitleaks, Semgrep, Trivy, publicação e deploy com gates |
| [Observabilidade Azure](docs/OBSERVABILIDADE.md) / [AWS](docs/OBSERVABILIDADE-AWS.md) | Quatro métricas, configuração local, alerta e recuperação, com alvos e dados separados |
| [Documento Cloud](docs/CLOUD.md) / [Status Cloud](docs/STATUS-CLOUD.md) | Rubrica, arquitetura, resultados comprovados e pendências |
| [Checkpoint Azure](evidencias/cloud/manifest.json) / [evidências AWS](evidencias/aws/security-passed-summary.json) | Provas identificadas por provedor, URL, horário e revisão; ensaio controlado AWS e recuperação aprovados |

A interface não exige conta, CPF, nome, telefone ou geolocalização. Não informe dados pessoais na pergunta. O aplicativo não mantém histórico de conversas; a operação Cloud deve preservar essa minimização nos logs. Em falha, a interface informa indisponibilidade e permite tentar novamente; o [site da SPTrans](https://www.sptrans.com.br/) é uma alternativa externa.

A Azure já teve publicação demo, containers, pesos, pipeline, métricas, disparo e recuperação verificados. A AWS Sandbox, aceita pelo professor **conforme relato de Pedro**, também tem infraestrutura, CI, HTTPS, inferência, runtime, métricas e ensaio controlado de alerta/recuperação comprovados; somente a consolidação e revisão do PDF Cloud continuam pendentes. A consulta SPTrans real passou em preflight restrito na Azure, mas a publicação HTTP live aguarda revisão e validação final. O envio acadêmico continua com um integrante. O prazo publicado é **19/11/2026 às 23h55**; Pedro/equipe realizam a submissão e conferem a divergência Teams/portal da disciplina Cloud. A preparação técnica não equivale à submissão.
