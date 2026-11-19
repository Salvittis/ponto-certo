# Estado da IA — Ponto Certo 0.1.0

Atualizado em 19/11/2026. **A aplicação pública na [Azure](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) foi promovida para LIVE e validada por HTTP e formulário real às 11:03–11:06 (America/Sao_Paulo)**, na revisão `8b1e298a101eb9b90bf723efad268449381e2552`. A jornada descobriu linhas e pontos na SPTrans e exibiu uma previsão com fonte e atualização. O [AWS Sandbox](https://54-210-161-95.sslip.io/) permanece **DEMO**, na mesma revisão, com ensaio de indisponibilidade/recuperação comprovado. São evidências históricas de integração, sem garantia de previsão ou disponibilidade futura. Conforme aceite do professor relatado por Pedro, AWS Sandbox é a frente de entrega Cloud; Azure permanece destinada à IA. A avaliação original e seus artefatos estão preservados. Submissão acadêmica não realizada.

## Funciona e foi executado

- Mesma aplicação em `ponto-certo/`: FastAPI, frontend HTML/CSS/JS, LLM **local** Qwen2.5-1.5B Q4_K_M no llama.cpp b12464, recuperação TF-IDF e agente de ferramentas restritas.
- Interface → API → recuperação/ferramenta → modelo real → resposta: verificada no navegador em consulta documental, chegada sintética e esclarecimento. Capturas desktop e viewport móvel 390×844 em `evidencias/interface-*.jpg`. Avaliação visual manual, sem auditoria completa WCAG ou usuário com leitor de tela.
- Smoke HTTP real passou em `http://127.0.0.1:8000`, cobrindo saúde, prontidão, configuração, documental e chegada; `evidencias/smoke-local.json` preserva data/hora e checks.
- Smoke HTTP **público** passou nos cinco checks em 19/11/2026, 09:23:20–09:23:36 (America/Sao_Paulo): saúde, prontidão, configuração, pergunta documental e chegada sintética. [Evidência](../evidencias/smoke-publico-ia.json). Respostas documental/chegada: 7,664 s e 8,390 s, respectivamente; são amostras únicas, sem benchmark ou SLA. Versão 0.1.0, revisão implantada validada `48752d037ee6b7feaee1806ab00dc60e465ad745`, modo demo; `/readyz` informa `sptrans_live_verified=false`.
- Jornada no **navegador público** concluída em 19/11/2026 às 09:25 (America/Sao_Paulo): envio real do formulário para chegada demo e pergunta documental, ambas com estado `ok`; fontes, avisos de simulação e atualização visíveis. A fonte documental pública respondeu HTTP 200. [Manifesto](../evidencias/jornada-publica-ia.json), [chegada](../evidencias/interface-publica-chegada.jpg) e [documental](../evidencias/interface-publica-documental.jpg). Não é reexecução dos 24 casos nem auditoria completa de acessibilidade.
- [Identidade pública](../evidencias/identidade-publica-ia.json) confirmada nas três rotas às 09:24: serviços locais nas portas 8000, 8002 e 8081 estavam fechados. O funcionamento público observado não dependia desses serviços locais. Esse checkpoint público era demo; a verificação externa SPTrans posterior está discriminada abaixo.
- No checkpoint anterior aos novos patches de integração live, 19 testes automatizados API/admissão passaram: validação, não exposição de tokens/entrada inválida, limite 8 KiB/fila de 2 consultas/liberação após falha, métricas Bearer, saúde/prontidão separadas, falha de modelo e assets. Usam modelo falso isolado; **não** são apresentados como inferência real.
- Modelo GGUF SHA256 verificado. Carregamento local observado 9,477 s; RSS instantâneo 1.106.160 KiB (~1,05 GiB), Mac Apple M4/16GB. Não extrapolar para Cloud CPU; `evidencias/modelo-local.json` distingue observação e estimativa.
- Base: 18 trechos com fonte/data/condições de uso. Recall@1=13/14 (92,86%), recall@3=14/14 (100%); limiar 0,05 calibrado em DEV. Negativas 4/4 rejeitadas; corpus e amostra pequenos.
- Avaliação real: DEV6 + TEST24, cada qual três configurações com mesmos pesos/parâmetros. Saídas brutas, finais, hashes e condições em `avaliacao/runs/{dev-v1,test-v1}`. TEST foi reservado antes das saídas e não usado para ajustar implementação.

## Jornada pública LIVE na Azure

A [implantação](../evidencias/cloud/azure-live-deployment.json) confirmou a revisão `8b1e298a101eb9b90bf723efad268449381e2552`, versão 0.1.0, modo `live` e os digests das imagens. A execução [44536511956, tentativa 1](https://github.com/Salvittis/ponto-certo/actions/runs/44536511956/attempts/1) aprovou nove jobs e publicou Azure/AWS em DEMO. Na [tentativa 2](https://github.com/Salvittis/ponto-certo/actions/runs/44536511956/attempts/2), somente o job de deploy Azure foi reexecutado para LIVE, preservando o mesmo commit e as imagens já construídas, verificadas e publicadas; AWS não foi reimplantada nessa promoção.

O [smoke HTTPS LIVE](../evidencias/cloud/azure-live-public.json) passou em 19/11/2026, **11:03:49–11:04:11** (São Paulo): saúde, prontidão, configuração, duas consultas de previsão e descoberta de linhas. A consulta 35274/sentido 2/ponto 614432 retornou `not_found`, resultado vazio válido; a consulta 2506/sentido 1/ponto 7014417 retornou `ok`. Ambas exibiram fonte e atualização, sem texto de demonstração. A busca de linhas retornou quatro opções. As observações são amostras únicas, sem benchmark ou SLA.

Na [jornada pelo formulário público](../evidencias/jornada-publica-live.json), às **11:05–11:06**, a busca `8000` retornou quatro registros; a seleção **2506, sentido 1** trouxe **14 pontos**; a seleção **7014417 — ANGELICA B/C** resultou em `ok`, previsão **11:12**, aproximadamente **6 minutos no relógio da consulta**, com fonte SPTrans Olho Vivo e atualização **11:06**. O aviso de simulação não estava presente. A previsão é histórica e não garante chegada. As cinco capturas registram [início](../evidencias/interface-publica-live-inicio.jpg), [linhas](../evidencias/interface-publica-live-linhas.jpg), [pontos](../evidencias/interface-publica-live-pontos.jpg), [formulário completo](../evidencias/interface-publica-live-completa.jpg) e [chegada](../evidencias/interface-publica-live-chegada.jpg).

Às **11:06:52**, `/healthz`, `/readyz` e `/api/config` confirmaram a mesma revisão, e a configuração confirmou `live`. **`sptrans_live_verified=false` em `/readyz` é o contrato desse endpoint:** ele verifica configuração/modelo, sem fazer a autenticação e consulta externas. A comprovação do acesso real é a jornada HTTP/UI e seus resultados, não o sinal isolado de prontidão. Esta validação posterior não reexecuta nem substitui o TEST24.

## Recuperação operacional pública na Azure

A frente Cloud concluiu o ensaio em 19/11/2026 na mesma revisão `48752d037ee6b7feaee1806ab00dc60e465ad745`: somente o container LLM foi parado/iniciado, entre **12:27:30 e 12:29:31 UTC** (09:27:30–09:29:31 de São Paulo), sem reboot da VM. Dois alertas estavam em `firing` às **12:28:51 UTC**; a API permaneceu viva, prontidão e pergunta retornaram 503 e a interface mostrou indisponibilidade. [Ensaio](../evidencias/cloud/alert-exercise.json), [contrato durante falha](../evidencias/cloud/public-model-unavailable.json) e [captura](../evidencias/cloud/screenshots/public-unavailable.jpg).

Após a restauração automática, prontidão 200, alertas resolvidos e três containers saudáveis foram observados. O [smoke real posterior](../evidencias/cloud/smoke-public-recovered.json) passou **5/5** até **12:30:41 UTC** (09:30:41 de São Paulo); documental 14,162 s e chegada demo 12,675 s, amostras de integração sem benchmark. [Recuperação](../evidencias/cloud/observability-recovered.json), [interface restaurada](../evidencias/cloud/screenshots/public-recovered.jpg) e [reinício](../evidencias/cloud/restart-public.json) confirmam os mesmos digests e pesos de 1.117.320.736 bytes com SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`. Isso acrescenta validação operacional e não reexecuta nem modifica o experimento TEST24.

## Execução e recuperação operacional no AWS Sandbox

A [aplicação AWS](https://54-210-161-95.sslip.io/) foi observada no navegador com revisão **`60aeeddc0509cf6c82c65485f67fae67ad494a62`**, modo **demo**, em 19/11/2026, às 10:07–10:08 (America/Sao_Paulo). A chegada simulada exibiu fonte, avisos e atualização. A captura do pipeline mostrou a execução histórica [44528188191](https://github.com/Salvittis/ponto-certo/actions/runs/44528188191) em sucesso, com nove jobs; isso não antecipa o resultado de outro commit ou dos patches posteriores. [Manifesto das observações](../evidencias/aws/browser-observations.json).

O ensaio controlado, conduzido por Cloud, parou somente a LLM AWS às **13:21:35 UTC** e solicitou reinício às **13:23:36 UTC** (10:21:35–10:23:36 de São Paulo), com restauração automática. Durante a falha, o navegador registrou `PublicReadyUnavailable` e `ModelNotReady` em `FIRING`, com coleta de métricas ativa. Após a restauração, as três regras estavam `INACTIVE` às 10:24:14; o dashboard às 10:24:35 mostrou **prontidão/modelo/coleta/alertas = 1/1/1/0**. Os snapshots do dashboard foram 1/1/1/0 no baseline visual, 0/0/1/2 durante a falha e 1/1/1/0 após recuperação. São observações pontuais, não prova de disponibilidade contínua.

Um incidente anterior **não provocado**, entre aproximadamente 10:13 e 10:17, está separado no mesmo manifesto: houve divergência entre navegador e monitor, e a causa não foi estabelecida por essas capturas. Não foi apresentado como ensaio controlado nem ocultado no histórico dos gráficos. O ensaio AWS acrescenta evidência operacional ao produto e não reexecuta o TEST24.

No **segundo ensaio**, já na revisão `8b1e298a101eb9b90bf723efad268449381e2552`, o baseline visual às 10:55:35 era 1/1/1/0; a janela também continha a breve queda do deploy. Cloud enviou o comando de parada temporária da LLM às **10:56:51**, por 120 segundos, e fez uma consulta que retornou 503. Às **10:58:37**, `PublicReadyUnavailable` e `ModelNotReady` estavam em `FIRING`, `MetricsUnavailable` em `INACTIVE`, e o dashboard mostrou **0/0/1/2**. O manifesto registra aumento visual da taxa de erro e o snapshot JSON informado por Cloud de **11,11%**, restrito à janela do ensaio. Às **10:59:28**, as três regras estavam `INACTIVE` e o dashboard voltou a **1/1/1/0**. [Observações v2](../evidencias/aws/browser-observations.json), [falha](../evidencias/aws/screenshots/dashboard-firing-v2.jpg) e [recuperação](../evidencias/aws/screenshots/dashboard-recovered-v2.jpg).

O [formulário AWS](../evidencias/aws/screenshots/public-response-v2.jpg) retornou chegada **DEMO** com fonte sintética e atualização visíveis às **11:02:15**, e a identidade da revisão foi confirmada após a captura. O sucesso da Azure LIVE não altera a modalidade dessa demonstração AWS.

## Resultado original observado — TEST24

| Medida no TEST24 | Sem contexto | RAG simples | Agente |
|---|---:|---:|---:|
| Acerto por propriedades automáticas | 9/24 | 12/24 | 15/24 |
| Acerto semântico auditado | 9/24 | 10/24 | 15/24 |
| Afirmações finais sem suporte | 2/24 | 3/24 | 0/24 |
| Fabricações finais claras | 1/24 | 3/24 | 0/24 |
| JSON final válido | 24/24 | 24/24 | 24/24 |
| JSON bruto válido/chamadas | 24/24 | 24/24 | 17/17 |

Um agente auditor revisou todas as saídas; sem dupla revisão humana. No agente, 7 casos não chamaram a LLM e 6 usaram fallback extrativo. A geração bruta do agente alucinou uma chegada; o software a removeu. Ganho pertence ao sistema completo, não a treinamento de pesos. Zero em 24 não garante ausência geral. Fontes presentes são diferentes de fontes que sustentam a resposta. Uma consulta UI concorrente limita a interpretação de latência; não é benchmark de Cloud.

Cinco erros reais, causas e propostas estão em `avaliacao/runs/test-v1/audit.md`: chegada inventada por ordem adversarial, ID de trecho confundido com ônibus, horário inventado em retorno vazio, recusa excessiva do agente e status inadequado após fallback seguro. As propostas não foram aplicadas ao teste para fabricar melhora.

## Reproduzir

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock -r requirements-dev.txt
.venv/bin/python scripts/download_model.py
# Iniciar llama-server b12464 como descrito no README, porta privada 8081
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# Em outro terminal
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke.py --base-url http://127.0.0.1:8000 --output evidencias/smoke-repro.json
.venv/bin/python -m base.evaluate_retrieval
.venv/bin/python -m avaliacao.run --split test --output avaliacao/runs/test-repro
```

Use output novo para preservar os experimentos anteriores. A árvore de produção recebe alterações posteriores ao estudo; executar o teste congelado nela é uma regressão dessa nova versão, não um novo teste cego nem garantia de reproduzir os resultados originais. Para identificar o estudo original, use o manifesto e as saídas preservadas em `avaliacao/runs/test-v1`. Notebook `notebooks/avaliacao-ia.ipynb` executado: 6 células, 17 saídas salvas, nenhum erro; HTML e gráfico também gerados. Vídeo `evidencias/ponto-certo-demonstracao.mp4`: 32 segundos, 470 KB, quatro capturas reais, sem áudio e sem alegação de gravação contínua. Ambos são derivados das evidências reais, com método descrito nos seus arquivos. Servidores nativos locais foram encerrados após QA para liberar recursos aos testes Docker de Cloud; reinicialização descrita no README.

## Dados, acesso real e cobertura

A avaliação original usou a simulação autorizada enquanto não havia token: `dados/fixtures/sptrans-demo.json`, linha 8000-10, códigos 1273/34041, ponto demonstrativo 4200153 e relógio 19/11/2026 10:00. Ela continua congelada e não comprova operação real. Nenhuma previsão histórica foi indexada como atual.

Posteriormente, a conta/app **Ponto Certo - FIAP CitizenTech** foi cadastrada e a chave homologada/em uso foi guardada no `.env` local, ignorado pelo Git e com permissão `0600`. O valor do segredo não integra este registro. As seguintes etapas reais foram verificadas, cada uma com seu alcance:

| Etapa e horário de São Paulo, 19/11/2026 | Resultado observado | Evidência |
|---|---|---|
| Verificador independente, 09:54:24–09:54:25 | Autenticação `true`; busca `8000` retornou quatro registros. Serviço `tl=1`, sentidos/códigos 1/2506 e 2/35274. Duas consultas de previsão: a primeira vazia; **somente a segunda retornou uma previsão** | [JSON sanitizado](../evidencias/sptrans-verificacao-20261119T125425332800Z.json) |
| Adaptador da aplicação, 09:55:26 | `passed`, `mode=live`, `synthetic=false`; código 35274, ponto 614432, sentido 2, uma linha correspondente e uma previsão | [Adaptador real](../evidencias/sptrans-adaptador-real.json) |
| Preflight Azure, 10:08:44–10:08:58 | Duas verificações aprovadas: documental e chegada live. Ambas chamaram a LLM real, produziram JSON válido e usaram fallback extrativo. A consulta live teve uma previsão utilizável, fonte/telemetria recentes e `synthetic=false` | [Preflight no container](../evidencias/cloud/azure-live-preflight.json) |
| Preflight Azure com validação de idade após inferência, 10:56:32–10:56:54 | Três checks aprovados na revisão `8b1e298…`: documental; previsão vazia válida sem chamar a LLM; descoberta de quatro linhas reais com chamada à LLM e fallback extrativo. Nenhuma previsão utilizável nessa amostra | [Preflight posterior](../evidencias/cloud/azure-live-preflight-hardened.json) |
| HTTPS Azure público LIVE, 11:03:49–11:04:11 | Seis checks aprovados; uma consulta de previsão vazia, outra `ok`, quatro opções de linha e revisão confirmada | [HTTP público](../evidencias/cloud/azure-live-public.json) |
| Formulário Azure público LIVE, 11:05–11:06 | Quatro registros de linha, 14 pontos do sentido selecionado, previsão 11:12 com atualização 11:06; fonte e ressalva visíveis | [Jornada e identidade](../evidencias/jornada-publica-live.json) |

O primeiro preflight registrou `app_revision=60aeeddc0509cf6c82c65485f67fae67ad494a62` e escopo **`direct_engine_preflight_not_public_http`**: valida Engine, ferramenta e modelo no runtime Azure, mas **não** demonstra `/api/ask` público em live nem uma mudança já aplicada à interface. Tempos documental/live de 7,498 s e 6,870 s são duas amostras de integração, sem benchmark. A idade do relógio da fonte foi cerca de 51,7 s e a da telemetria exibida, 31,7 s naquela consulta.

Esses dados são evidências históricas. Uma parada por sentido não representa toda a linha; vazio não comprova falta de serviço e previsão não garante chegada. A presença de token ou `readyz` positivo não substitui autenticação e consulta reais. Condições oficiais e detalhe do primeiro acesso estão no [adendo SPTrans](SPTRANS-LIVE.md).

Para repetir o verificador, após o segredo estar configurado, sem colocá-lo na linha de comando:

```sh
.venv/bin/python -m scripts.verify_sptrans --query 8000
```

A promoção Azure LIVE e sua jornada HTTP/UI estão comprovadas nas evidências posteriores acima. Os registros antigos em DEMO e os preflights anteriores à promoção mantêm seus respectivos escopos. AWS continua DEMO; seus avisos de simulação permanecem necessários. Não reutilizar os códigos da fixture como cobertura presumida da API real.

## Contrato e versão para Cloud

Contrato v0.1.0 em `docs/CONTRATO-IA-CLOUD.md`, enviado ao agente Cloud; primeira versão executável comunicada em 19/11/2026. Mesmos modelo/runtime alinhados, dependências runtime fixadas, portas 8000/8081, health/readiness/config/metrics e smoke disponíveis. Cloud possui Docker/Compose, CI/CD, Terraform e observabilidade; não foram alterados por IA.

Repositório único: [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo), público. As revisões são **checkpoints**, não afirmação de que todo o trabalho posterior já foi publicado: Azure HTTP/UI/ensaio demo verificaram `48752d037ee6b7feaee1806ab00dc60e465ad745`; AWS demo e primeiro preflight direto Azure live registraram `60aeeddc0509cf6c82c65485f67fae67ad494a62`; Azure HTTP/UI LIVE e AWS DEMO com segundo ensaio verificaram `8b1e298a101eb9b90bf723efad268449381e2552`. Os artefatos de cada etapa documentam sua modalidade e horário. A identidade do estudo original permanece nos SHA256 de `avaliacao/runs/test-v1/manifest.json`; não havia commit durante o experimento. Cloud controla README, relatório Cloud, Git e a publicação da próxima versão.

## Pendências concretas

1. Pedro/integrante: conferir o conteúdo final e enviar os links no Teams até 19/11/2026 às 23h55. Não houve submissão.
2. Manter os links e serviços necessários disponíveis durante a correção, sob responsabilidade da equipe, preservando a distinção Azure LIVE / AWS DEMO. A promoção LIVE e as jornadas descritas estão comprovadas; não são pendências deste checkpoint. Railway da TBC permanece fora do escopo.

Nomes/RMs confirmados por Pedro: Filipe Prado Menezes RM98765; Cássio Eid Kobaysahi Yonetsuka RM99678; Pedro Henrique Salvitti Habiro RM88166. Nenhum nome ou RM foi inferido.

### Ajuste posterior ao experimento

O primeiro ajuste posterior ao estudo acrescentou limite HTTP de 8 KiB, duas consultas simultâneas por processo e 10 s para envio do corpo, com `app/limits.py` e alteração de `app/main.py`. Os 19 testes e o smoke daquele checkpoint validaram essa fronteira. **A produção agora também recebe patches de Engine/Transit posteriores ao experimento**, portanto não se afirma que seus hashes ou comportamento permaneçam idênticos ao TEST24. O manifesto, corpus, gabarito e resultados originais não foram reescritos; validações posteriores precisam identificar sua própria versão e não substituem o placar acadêmico original.

Smoke da integração em Docker realizado por Cloud em `http://127.0.0.1:8002`: cinco checks passaram, resposta documental em 7,974 s e chegada em 4,705 s, em `evidencias/cloud/smoke-compose.json`. Essa evidência é local em containers e antecede o ajuste de admissão HTTP; a verificação pública posterior está separada em `evidencias/smoke-publico-ia.json`.

Desconexão durante o envio é tratada com resposta vazia 499, sem inferência nem falso 500 na telemetria. Teste da aplicação ASGI completa reproduziu e verificou a correção; contador de capacidade é liberado.
