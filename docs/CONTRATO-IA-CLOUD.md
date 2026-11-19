# Contrato IA–Cloud — Ponto Certo v0.1.0

Responsável IA: Pedro/Salvitti. Cloud mantém infraestrutura, Docker/Compose, Terraform, CI/CD e observabilidade. Mesma aplicação em `ponto-certo/`, sem outro repositório. Contrato inicial de 19/11/2026; commit será registrado após validação. Alterações incompatíveis exigem coordenação entre agentes.

## Execução

Python 3.11+; `python -m venv .venv`; `.venv/bin/pip install -r requirements.lock`; `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`.
Frontend HTML/CSS/JS servido por FastAPI em `/`. Sem build Node, banco ou conta do cidadão.
LLM autohospedada via llama.cpp `llama-server -m /models/qwen2.5-1.5b-instruct-q4_k_m.gguf --alias qwen2.5-1.5b-instruct --host 127.0.0.1 --port 8081 -c 4096 -np 1 --metrics`.
Cloud usa nome DNS privado do serviço no `LLM_BASE_URL`; somente porta web é pública. A API compatível OpenAI é protocolo local, não serviço comercial.

## Modelo e recursos

Qwen/Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`, Apache-2.0 conforme [model card oficial](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF). Arquivo `qwen2.5-1.5b-instruct-q4_k_m.gguf` (~1,1 GB). llama.cpp b12464, MIT, [release oficial](https://github.com/ggml-org/llama.cpp/releases/tag/b12464). Downloads iniciais exigem rede, inferência posterior funciona offline.
Estimativa inicial: 2–4 GB RAM para pesos/cache/contexto e API, CPU 2+ vCPUs; GPU opcional. Disco persistente >=2 GB para pesos; build pode exigir mais. Tempos e RSS observados serão registrados em `evidencias/modelo-local.json`; estimativa não é medição de Cloud. Contexto 4096, 1 slot, temperature=0, seed=42, max_tokens=450.

## Rotas

* `GET /healthz`: 200 processo vivo + versão; não promete LLM.
* `GET /readyz`: 200 dependências prontas; 503 se modelo ausente ou credencial ausente no modo live. Em demo explicita dados simulados. Não faz inferência completa a cada probe.
* `GET /api/config`: modo, modelo, versão e cobertura; nenhum segredo.
* `GET /metrics`: formato Prometheus. Tráfego, latência, erros, requisições/inferências ativas, chamadas e falhas do modelo; sem pergunta, IP, ponto ou rota dinâmica como label. Protegido por Bearer `METRICS_TOKEN`; 503 se não configurado e 401 sem credencial correta.
* `POST /api/ask`: `{"question":"Quando chega?","line_code":1273,"stop_code":4200153,"direction":1}`. Question 1–1000 caracteres; códigos positivos opcionais; direction 1 ou 2. Apenas configuração agent na API pública.

Resposta: `{"status":"ok|not_found|clarification|unavailable","answer":"texto","sources":[{"id":"...","title":"...","url":"https://..."}],"updated_at":"ISO8601 ou null","data_mode":"demo|live|documental","model":"qwen2.5-1.5b-instruct","request_id":"UUID","warnings":[],"options":[]}`. Options são objetos de linha/ponto retornados para escolha. `not_found` não significa ausência de ônibus; `clarification` pede dados; `unavailable` indica falha/ausência de dependência. 422 entrada inválida; 503 para indisponibilidade; 200 demais estados. Não retorna stack trace, prompts brutos ou tokens. JSON público descrito em `/openapi.json`.

## Configuração

| Variável | Padrão | Segredo |
|---|---|---|
| DATA_MODE | demo (`live` exige token) | não |
| SPTRANS_TOKEN | vazio | **sim**, somente servidor; nunca logar URL de autenticação |
| LLM_BASE_URL | http://127.0.0.1:8081/v1 | não; rede privada |
| LLM_MODEL | qwen2.5-1.5b-instruct | não |
| LLM_TIMEOUT_SECONDS | 90 | não |
| RETRIEVAL_THRESHOLD | 0.05, sujeito calibração dev | não |
| MAX_DATA_AGE_SECONDS | 180 | não |
| APP_VERSION | 0.1.0 | não |
| APP_REVISION | local; Cloud informa commit | não |
| METRICS_TOKEN | vazio, métricas fechadas | **sim**, Bearer de scraping |

## Persistência, privacidade e limites

Pesos incorporados na imagem LLM de Cloud, persistentes pelo digest da imagem; base documental pequena versionada; fixtures versionadas são **sintéticas**, não captura ao vivo. Sem histórico de conversas, geolocalização, usuários, banco ou analytics. Cookie de sessão SPTrans apenas na memória. Cache documental reconstruído no startup. Não persistir previsões ao vivo em índice RAG. Avaliação usa dados sintéticos sem pessoais. Logs sem acesso/query strings; o proxy Cloud deve seguir mesma política. Entrada livre pode conter dados pessoais: avisar para não informar e não registrar corpo.

Recorte inicial demonstrativo: exemplo 8000-10, códigos por sentido 1273/34041 e ponto sintético 4200153, sem alegação de cobertura real atual. Live descobre linhas e paradas retornadas pela SPTrans; documentação limita paradas a corredores. Validação real dessa cobertura depende de credencial. Sem baldeações, mapa de itinerário completo, CV, PIR ou RPA implementados nesta frente.

## Validação e coordenação

`python -m pytest -q`, `python scripts/smoke.py --base-url http://127.0.0.1:8000` e `python -m avaliacao.run --split test --output avaliacao/runs/reproducao` (pesos carregados). Testes determinísticos isolam dependências; smoke e avaliação usam modelo real. Cloud deve executar smoke contra URL pública e preservar resultado separado do local. No modo demo readiness não atesta SPTrans real. Consulta SPTrans real pendente. Vídeo local em `evidencias/ponto-certo-demonstracao.mp4`, montagem de capturas reais, publicação com o repositório. Instrumentação exposta e contrato enviado ao agente Cloud; nenhuma infraestrutura alterada pela frente IA.

## Identidade verificada dos pesos

GGUF: 1.117.320.736 bytes, SHA256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, conferido no download local. Build llama.cpp alinhado b12464. Métricas: `ponto_certo_http_requests_total{method,route,status}`, `ponto_certo_http_request_duration_seconds`, `ponto_certo_llm_requests_total{outcome}`, `ponto_certo_llm_duration_seconds`, `ponto_certo_llm_inflight`, `ponto_certo_llm_capacity`, `ponto_certo_model_ready`; `process_resident_memory_bytes` disponível no coletor padrão em Linux. Health/config/readiness incluem `revision`. Readiness testa listagem do modelo, não geração nem autenticação real SPTrans.
