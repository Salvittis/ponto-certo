# Contrato IA–Cloud — Ponto Certo v0.1.0

Responsável IA: Pedro/Salvitti. Cloud mantém infraestrutura, Docker/Compose, Terraform, CI/CD e observabilidade. Mesma aplicação em `ponto-certo/`, sem outro repositório. Contrato inicial de 19/11/2026, aplicação v0.1.0. As evidências abaixo identificam cada revisão observada: primeira validação Azure em `48752d037ee6b7feaee1806ab00dc60e465ad745`; primeira validação AWS e preflight real Azure em `60aeeddc0509cf6c82c65485f67fae67ad494a62`; validação operacional corrigida e **Azure pública LIVE** em `8b1e298a101eb9b90bf723efad268449381e2552`. Alterações incompatíveis exigem coordenação entre agentes.

A Azure permanece como hospedagem pública da IA e teve **LIVE confirmado por HTTP e navegador entre 11:03 e 11:06 de 19/11/2026 (São Paulo)**. Conforme relato de Pedro sobre aceite do professor, AWS Academy Sandbox é a frente de entrega Cloud e permanece em **DEMO**, com monitoramento e recuperação verificados. Os detalhes e a validade temporária do Sandbox constam nas evidências de Cloud. Os preflights internos são registros separados; a promoção pública está comprovada no adendo final deste contrato.

## Execução

Reprodução fixada em Python 3.12; `python3.12 -m venv .venv`; `.venv/bin/pip install -r requirements.lock`; `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
Frontend HTML/CSS/JS servido por FastAPI em `/`. Sem build Node, banco ou conta do cidadão.
LLM autohospedada via llama.cpp `llama-server -m /models/qwen2.5-1.5b-instruct-q4_k_m.gguf --alias qwen2.5-1.5b-instruct --host 127.0.0.1 --port 8081 -c 4096 -np 1 --metrics`.
Cloud usa nome DNS privado do serviço no `LLM_BASE_URL`; somente porta web é pública. A API compatível OpenAI é protocolo local, não serviço comercial.

## Modelo e recursos

Qwen/Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`, Apache-2.0 conforme [model card oficial](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF). Arquivo `qwen2.5-1.5b-instruct-q4_k_m.gguf` (~1,1 GB). llama.cpp b12464, MIT, [release oficial](https://github.com/ggml-org/llama.cpp/releases/tag/b12464). Downloads iniciais exigem rede, inferência posterior funciona offline.
Estimativa inicial: 2–4 GB RAM para pesos/cache/contexto e API, CPU 2+ vCPUs; GPU opcional. Disco persistente >=2 GB para pesos; build pode exigir mais. Carregamento local de 9,477 s e RSS instantâneo de 1.106.160 KiB registrados em `evidencias/modelo-local.json` (Apple M4/16 GB, Metal); a estimativa de recursos não é medição de memória/pico da implantação Cloud. Contexto 4096, 1 slot, temperature=0, seed=42, max_tokens=450.

## Rotas

* `GET /healthz`: 200 processo vivo + versão; não promete LLM.
* `GET /readyz`: 200 dependências prontas; 503 se modelo ausente ou credencial ausente no modo live. Em demo explicita dados simulados. Não faz inferência completa a cada probe.
* `GET /api/config`: modo, modelo, versão e cobertura; nenhum segredo.
* `GET /metrics`: formato Prometheus. Tráfego, latência, erros, requisições/inferências ativas, chamadas e falhas do modelo; sem pergunta, IP, ponto ou rota dinâmica como label. Protegido por Bearer `METRICS_TOKEN`; 503 se não configurado e 401 sem credencial correta.
* `POST /api/ask`: `{"question":"Quando chega?","line_code":1273,"stop_code":4200153,"direction":1}`. Question 1–1000 caracteres; códigos positivos opcionais; direction 1 ou 2. Apenas configuração agent na API pública.

Resposta: `{"status":"ok|not_found|clarification|unavailable","answer":"texto","sources":[{"id":"...","title":"...","url":"https://..."}],"updated_at":"ISO8601 ou null","data_mode":"demo|live|documental","model":"qwen2.5-1.5b-instruct","request_id":"UUID","warnings":[],"options":[]}`. Options são objetos de linha/ponto retornados para escolha. `not_found` não significa ausência de ônibus; `clarification` pede dados; `unavailable` indica falha/ausência de dependência. 408 envio do corpo excede 10 s; 413 corpo >8 KiB; 429 duas consultas já em andamento (1 slot de inferência +1 fila, por processo; usar 1 worker); 422 entrada inválida; 503 para indisponibilidade; 200 demais estados. Não retorna stack trace, prompts brutos ou tokens. JSON público descrito em `/openapi.json`.

## Configuração

| Variável | Padrão | Segredo |
|---|---|---|
| DATA_MODE | demo (`live` exige token) | não |
| SPTRANS_TOKEN | vazio | **sim**, somente servidor; nunca logar URL de autenticação |
| LLM_BASE_URL | http://127.0.0.1:8081/v1 | não; rede privada |
| LLM_MODEL | qwen2.5-1.5b-instruct | não |
| LLM_TIMEOUT_SECONDS | 90 | não |
| RETRIEVAL_THRESHOLD | 0.05, calibrado em DEV | não |
| MAX_DATA_AGE_SECONDS | 180 | não |
| APP_VERSION | 0.1.0 | não |
| APP_REVISION | local; Cloud informa commit | não |
| METRICS_TOKEN | vazio, métricas fechadas | **sim**, Bearer de scraping |

## Persistência, privacidade e limites

Pesos incorporados na imagem LLM de Cloud, persistentes pelo digest da imagem; base documental pequena versionada; fixtures versionadas são **sintéticas**, não captura ao vivo. Sem histórico de conversas, geolocalização, usuários, banco ou analytics. Cookie de sessão SPTrans apenas na memória. Cache documental reconstruído no startup. Não persistir previsões ao vivo em índice RAG. Avaliação usa dados sintéticos sem pessoais. Logs sem acesso/query strings; o proxy Cloud deve seguir mesma política. Entrada livre pode conter dados pessoais: avisar para não informar e não registrar corpo.

Recorte demonstrativo: exemplo 8000-10, códigos por sentido 1273/34041 e ponto sintético 4200153, sem alegação de cobertura real atual. Live descobre linhas e paradas retornadas pela SPTrans; documentação limita paradas a corredores. A consulta real de 19/11/2026 às 09:54 (São Paulo) descobriu a linha `lt=8000, tl=1`, códigos 2506/35274, com 14/13 paradas nos sentidos 1/2. O ponto 7014417 retornou vazio válido; 614432 retornou uma previsão histórica. Isso comprova cobertura naquele instante, não disponibilidade permanente. [Verificação e condições de uso](SPTRANS-LIVE.md). Sem baldeações, mapa de itinerário completo, CV, PIR ou RPA implementados nesta frente.

## Validação e coordenação

`python -m pytest -q`, `python scripts/smoke.py --base-url http://127.0.0.1:8000` e `python -m avaliacao.run --split test --output avaliacao/runs/reproducao` (pesos carregados). Testes determinísticos isolam dependências; smoke e avaliação usam modelo real. O smoke contra a [URL pública](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) foi executado em 19/11/2026, 09:23:20–09:23:36 (America/Sao_Paulo), com cinco checks aprovados e evidência separada em [smoke-publico-ia.json](../evidencias/smoke-publico-ia.json). A revisão observada em health/config/readiness foi `48752d037ee6b7feaee1806ab00dc60e465ad745`; modo demo, modelo Qwen e aplicação v0.1.0. Pergunta documental e chegada sintética levaram 7,664 s e 8,390 s; são amostras únicas de integração, não benchmark de desempenho. Readiness não atesta autenticação real SPTrans, inclusive no modo live; a verificação real posterior está registrada no adendo abaixo. Vídeo local em `evidencias/ponto-certo-demonstracao.mp4`, montagem de capturas reais, publicação com o repositório. Instrumentação exposta e contrato enviado ao agente Cloud; nenhuma infraestrutura alterada pela frente IA.

A jornada pelo navegador público também foi verificada às 09:25 (America/Sao_Paulo) em 19/11/2026, com envio real do formulário para chegada demo e pergunta documental. Ambas retornaram `ok`, com fontes e avisos visíveis; a chegada exibiu atualização e a fonte documental respondeu HTTP 200. [Jornada pública](../evidencias/jornada-publica-ia.json), [captura da chegada](../evidencias/interface-publica-chegada.jpg) e [captura documental](../evidencias/interface-publica-documental.jpg). A [verificação de identidade](../evidencias/identidade-publica-ia.json) registrou as portas locais 8000/8002/8081 fechadas enquanto a aplicação pública respondia, distinguindo a publicação dos serviços locais. O ensaio posterior de indisponibilidade e recuperação integra as evidências operacionais descritas abaixo, sem substituir essa jornada ou o experimento de IA.

## Recuperação pública verificada na Azure

Em 19/11/2026, somente o container LLM sofreu stop/start, de **12:27:30 a 12:29:31 UTC**. A API permaneceu em `/healthz` 200, enquanto `/readyz` e a pergunta retornaram 503 com indisponibilidade explícita. Dois alertas estavam em `firing` às **12:28:51 UTC**. A restauração automática foi confirmada com prontidão 200, ausência de alertas ativos, três serviços saudáveis e [smoke com LLM real 5/5](../evidencias/cloud/smoke-public-recovered.json) concluído às **12:30:41 UTC**. [Registro do ensaio](../evidencias/cloud/alert-exercise.json), [falha](../evidencias/cloud/public-model-unavailable.json), [recuperação](../evidencias/cloud/observability-recovered.json) e [comparação após reinício](../evidencias/cloud/restart-public.json).

As mesmas referências de imagem e o SHA-256/tamanho dos pesos foram preservados. Não houve reboot da VM nem reinício do proxy; esse ensaio não comprova recuperação de perda do host ou reemissão de certificados. A avaliação local original e seus hashes continuam preservados. As capturas [indisponível](../evidencias/cloud/screenshots/public-unavailable.jpg) e [recuperada](../evidencias/cloud/screenshots/public-recovered.jpg) complementam o comportamento funcional observado.

## Identidade verificada dos pesos

GGUF: 1.117.320.736 bytes, SHA256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, conferido no download local. Build llama.cpp alinhado b12464. Métricas: `ponto_certo_http_requests_total{method,route,status}`, `ponto_certo_http_request_duration_seconds`, `ponto_certo_llm_requests_total{outcome}`, `ponto_certo_llm_duration_seconds`, `ponto_certo_llm_inflight`, `ponto_certo_llm_capacity`, `ponto_certo_model_ready`; `process_resident_memory_bytes` disponível no coletor padrão em Linux. Health/config/readiness incluem `revision`. Readiness testa listagem do modelo, não geração nem autenticação real SPTrans.

Primeiro ajuste posterior ao experimento: proteção de admissão HTTP adicionada em `app/limits.py` e registro em `main.py`, sem alterar naquele ajuste Engine, prompts, recuperação, ferramentas ou parâmetros. Avaliação original preservada; 19 testes de código passaram. O smoke público registrado acima validou a revisão `48752d037ee6b7feaee1806ab00dc60e465ad745`, que inclui essa proteção. Os ajustes posteriores de Engine/Transit e métricas têm validação operacional própria abaixo; não reescrevem o experimento original.


## Adendo operacional SPTrans e AWS — 19/11/2026

A credencial foi criada com autorização de Pedro e guardada em `.env` local com permissão 0600, ignorado pelo Git. Não publicar seu conteúdo. O comando `python -m scripts.verify_sptrans --query 8000` usa HTTPS, autentica e descobre códigos reais; limita as requisições e produz apenas evidência sanitizada. [Consulta real](../evidencias/sptrans-verificacao-20261119T125425332800Z.json) e [adaptador real](../evidencias/sptrans-adaptador-real.json). Consultas vazias são resultados válidos e não demonstram ausência de serviço.

O preflight de `scripts/preflight_live.py` executado dentro do container Azure às **13:08:44–13:08:58 UTC**, na revisão `60aeeddc0509cf6c82c65485f67fae67ad494a62`, autenticou e retornou uma previsão real utilizável, com consulta documental e chegada passando pela LLM autohospedada. Ambas usaram fallback extrativo após a validação da saída. [Preflight Azure](../evidencias/cloud/azure-live-preflight.json). Esse processo isolado não mudou o serviço público, ainda em DEMO nesse checkpoint. Na imagem que não inclui `scripts/`, executar o script público por stdin ou montagem somente leitura; injetar a credencial no ambiente protegido, nunca como argumento. Saída sanitizada e exit code devem ser preservados.

As guardas adicionais de produção para ponto divergente e telemetria antiga, inclusive tempo gasto na rede/inferência, são mudanças operacionais posteriores ao TEST24. Foram validadas em testes e na nova imagem antes da promoção LIVE e da jornada pública. Não apresentar o placar original como uma reavaliação dessa nova versão. Nas previsões, `updated_at` representa o relógio `hr` da API; a idade da observação do veículo `ta` é uma verificação separada. Descoberta de linhas/paradas usa o horário da consulta.

Na AWS, a jornada pública DEMO e o pipeline [44528188191](https://github.com/Salvittis/ponto-certo/actions/runs/44528188191) foram verificados no mesmo SHA `60aeedd`. O ensaio conduzido por Cloud parou apenas a LLM às **13:21:35 UTC** e solicitou seu retorno às **13:23:36 UTC**. Dois alertas dispararam, enquanto a coleta da API permaneceu ativa. Após a restauração, o navegador mostrou prontidão/modelo/coleta em 1 e alertas em 0; Prometheus mostrou três regras inativas. [Manifesto visual com horários e hashes](../evidencias/aws/browser-observations.json), [falha](../evidencias/aws/screenshots/alerts-firing.jpg) e [recuperação](../evidencias/aws/screenshots/dashboard-recovered.jpg). Um incidente anterior de conectividade/coleta foi documentado separadamente; o snapshot de baseline indica estado recuperado, sem afirmar que toda a janela histórica estava saudável.

## Checkpoint público LIVE e operação corrigida

A revisão **`8b1e298a101eb9b90bf723efad268449381e2552`** passou 125 testes automatizados e os nove jobs da [tentativa 1 do pipeline 44536511956](https://github.com/Salvittis/ponto-certo/actions/runs/44536511956/attempts/1). Aplicação, LLM e proxy foram analisados antes da publicação. Uma vulnerabilidade HIGH em um supervisor sem uso havia bloqueado a imagem anterior; a remoção preservou o llama-server e os pesos, sem relaxar os controles. [Bloqueio](../evidencias/aws/screenshots/pipeline-blocked-current.jpg) e [aprovação](../evidencias/aws/screenshots/pipeline-passed-v2.jpg).

O [preflight da imagem corrigida](../evidencias/cloud/azure-live-preflight-hardened.json), às 10:56 de São Paulo, recebeu vazio válido para 35274/614432/sentido 2 e comprovou a integração fonte real + LLM pela descoberta de quatro linhas. Não houve repetição para obter um resultado mais conveniente. A [promoção Azure](../evidencias/cloud/azure-live-deployment.json) usou a tentativa 2 apenas do job Azure, mantendo o mesmo commit e os mesmos digests aprovados; AWS não foi reimplantada nessa promoção. O token ficou no ambiente protegido de produção e o modo público passou a `live`.

O [HTTP público real](../evidencias/cloud/azure-live-public.json) passou seis checks entre 11:03:49 e 11:04:11 (São Paulo): identidade/configuração, retorno vazio para 35274/614432, previsão disponível para 2506/7014417 e descoberta de linhas. A [jornada no navegador](../evidencias/jornada-publica-live.json) confirmou seleção a partir dos retornos: quatro opções de linha; código 2506/sentido 1; 14 paradas; ponto ANGELICA B/C, código 7014417; resposta `ok` com previsão histórica 11:12, aproximadamente seis minutos, e atualização informada 11:06. [Captura da resposta real](../evidencias/interface-publica-live-chegada.jpg). Esses horários descrevem o instante verificado e não devem ser reutilizados para planejar uma viagem posterior. Previsão continua sem garantia de chegada.

`/readyz` mantém `sptrans_live_verified=false` por contrato: não faz autenticação/consulta à fonte a cada probe. O sucesso da integração é demonstrado pelas evidências HTTP e UI acima, não pela mera presença do token. Saúde, prontidão e configuração foram novamente lidas após a jornada e confirmaram a revisão 8b1e298, modo live e dependências prontas.

Na AWS, a mesma revisão corrigida permaneceu DEMO. O [segundo ensaio](../evidencias/aws/hardened/alert-exercise.json) confirmou dois alertas e **11,11% de erro** após a primeira consulta 503, corrigindo a falta de amostra inicial do contador. A [recuperação](../evidencias/aws/hardened/observability-recovered.json) e [captura final](../evidencias/aws/screenshots/dashboard-recovered-v2.jpg) registram prontidão/modelo/coleta em 1 e alertas em 0. A [resposta pública DEMO](../evidencias/aws/screenshots/public-response-v2.jpg) também foi reenviada e validada. A avaliação A/B/C continua congelada e separada dessas mudanças operacionais. Submissão acadêmica e manutenção dos links durante a correção cabem à equipe.
