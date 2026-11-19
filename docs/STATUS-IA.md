# Estado da IA — Ponto Certo 0.1.0

Atualizado em 19/11/2026. Aplicação e avaliação locais executadas; repositório/relatório/notebook/vídeo publicados. A integração HTTP, a jornada no navegador e a recuperação após indisponibilidade real da LLM foram validadas na **Azure**, em modo demo com modelo autohospedado real: [Ponto Certo](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com). A Azure permanece ativa para IA. Conforme aceite do professor relatado por Pedro, AWS Sandbox será a entrega Cloud; ainda não há execução AWS comprovada neste checkpoint. Consulta SPTrans ao vivo e submissão acadêmica permanecem pendentes.

## Funciona e foi executado

- Mesma aplicação em `ponto-certo/`: FastAPI, frontend HTML/CSS/JS, LLM **local** Qwen2.5-1.5B Q4_K_M no llama.cpp b12464, recuperação TF-IDF e agente de ferramentas restritas.
- Interface → API → recuperação/ferramenta → modelo real → resposta: verificada no navegador em consulta documental, chegada sintética e esclarecimento. Capturas desktop e viewport móvel 390×844 em `evidencias/interface-*.jpg`. Avaliação visual manual, sem auditoria completa WCAG ou usuário com leitor de tela.
- Smoke HTTP real passou em `http://127.0.0.1:8000`, cobrindo saúde, prontidão, configuração, documental e chegada; `evidencias/smoke-local.json` preserva data/hora e checks.
- Smoke HTTP **público** passou nos cinco checks em 19/11/2026, 09:23:20–09:23:36 (America/Sao_Paulo): saúde, prontidão, configuração, pergunta documental e chegada sintética. [Evidência](../evidencias/smoke-publico-ia.json). Respostas documental/chegada: 7,664 s e 8,390 s, respectivamente; são amostras únicas, sem benchmark ou SLA. Versão 0.1.0, revisão implantada validada `48752d037ee6b7feaee1806ab00dc60e465ad745`, modo demo; `/readyz` informa `sptrans_live_verified=false`.
- Jornada no **navegador público** concluída em 19/11/2026 às 09:25 (America/Sao_Paulo): envio real do formulário para chegada demo e pergunta documental, ambas com estado `ok`; fontes, avisos de simulação e atualização visíveis. A fonte documental pública respondeu HTTP 200. [Manifesto](../evidencias/jornada-publica-ia.json), [chegada](../evidencias/interface-publica-chegada.jpg) e [documental](../evidencias/interface-publica-documental.jpg). Não é reexecução dos 24 casos nem auditoria completa de acessibilidade.
- [Identidade pública](../evidencias/identidade-publica-ia.json) confirmada nas três rotas às 09:24: serviços locais nas portas 8000, 8002 e 8081 estavam fechados. O funcionamento público observado não dependia desses serviços locais. Consulta externa SPTrans continua não validada.
- 19 testes automatizados API/admissão passaram: validação, não exposição de tokens/entrada inválida, limite 8 KiB/fila de 2 consultas/liberação após falha, métricas Bearer, saúde/prontidão separadas, falha de modelo e assets. Usam modelo falso isolado; **não** são apresentados como inferência real.
- Modelo GGUF SHA256 verificado. Carregamento local observado 9,477 s; RSS instantâneo 1.106.160 KiB (~1,05 GiB), Mac Apple M4/16GB. Não extrapolar para Cloud CPU; `evidencias/modelo-local.json` distingue observação e estimativa.
- Base: 18 trechos com fonte/data/condições de uso. Recall@1=13/14 (92,86%), recall@3=14/14 (100%); limiar 0,05 calibrado em DEV. Negativas 4/4 rejeitadas; corpus e amostra pequenos.
- Avaliação real: DEV6 + TEST24, cada qual três configurações com mesmos pesos/parâmetros. Saídas brutas, finais, hashes e condições em `avaliacao/runs/{dev-v1,test-v1}`. TEST foi reservado antes das saídas e não usado para ajustar implementação.

## Recuperação operacional pública na Azure

A frente Cloud concluiu o ensaio em 19/11/2026 na mesma revisão `48752d037ee6b7feaee1806ab00dc60e465ad745`: somente o container LLM foi parado/iniciado, entre **12:27:30 e 12:29:31 UTC** (09:27:30–09:29:31 de São Paulo), sem reboot da VM. Dois alertas estavam em `firing` às **12:28:51 UTC**; a API permaneceu viva, prontidão e pergunta retornaram 503 e a interface mostrou indisponibilidade. [Ensaio](../evidencias/cloud/alert-exercise.json), [contrato durante falha](../evidencias/cloud/public-model-unavailable.json) e [captura](../evidencias/cloud/screenshots/public-unavailable.jpg).

Após a restauração automática, prontidão 200, alertas resolvidos e três containers saudáveis foram observados. O [smoke real posterior](../evidencias/cloud/smoke-public-recovered.json) passou **5/5** até **12:30:41 UTC** (09:30:41 de São Paulo); documental 14,162 s e chegada demo 12,675 s, amostras de integração sem benchmark. [Recuperação](../evidencias/cloud/observability-recovered.json), [interface restaurada](../evidencias/cloud/screenshots/public-recovered.jpg) e [reinício](../evidencias/cloud/restart-public.json) confirmam os mesmos digests e pesos de 1.117.320.736 bytes com SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`. Isso acrescenta validação operacional e não reexecuta nem modifica o experimento TEST24.

## Resultado final observado

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

Use output novo para preservar os experimentos anteriores. Notebook `notebooks/avaliacao-ia.ipynb` executado: 6 células, 17 saídas salvas, nenhum erro; HTML e gráfico também gerados. Vídeo `evidencias/ponto-certo-demonstracao.mp4`: 32 segundos, 470 KB, quatro capturas reais, sem áudio e sem alegação de gravação contínua. Ambos são derivados das evidências reais, com método descrito nos seus arquivos. Servidores nativos locais foram encerrados após QA para liberar recursos aos testes Docker de Cloud; reinicialização descrita no README.

## Dados e cobertura

Pedro confirmou ausência de token e autorizou simulação. Fixture sintética versionada em `dados/fixtures/sptrans-demo.json`: 8000-10, códigos 1273/34041, ponto demonstrativo 4200153, relógio 19/11/2026 10:00. Não é captura externa e não comprova operação/itinerário atual. Cenários normal, vazio, antigo e falha. Nenhuma previsão histórica foi indexada como atual.

Cliente live implementado com endpoints fixos, HTTPS, token só no servidor e verificação temporal. **Não validado contra SPTrans real.** Para concluir, obter chave na área oficial, configurar `SPTRANS_TOKEN` em segredo e `DATA_MODE=live`, descobrir linhas/pontos realmente retornados e registrar consulta sanitizada com `python -m scripts.capture_live --line CODIGO --stop CODIGO`. Não usar IDs demo como cobertura presumida.

## Contrato e versão para Cloud

Contrato v0.1.0 em `docs/CONTRATO-IA-CLOUD.md`, enviado ao agente Cloud; primeira versão executável comunicada em 19/11/2026. Mesmos modelo/runtime alinhados, dependências runtime fixadas, portas 8000/8081, health/readiness/config/metrics e smoke disponíveis. Cloud possui Docker/Compose, CI/CD, Terraform e observabilidade; não foram alterados por IA.

Repositório único: [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo), público. A [aplicação publicada](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) respondeu com `APP_VERSION=0.1.0` e `APP_REVISION=48752d037ee6b7feaee1806ab00dc60e465ad745` na validação de 19/11/2026. Esse é o SHA implantado e testado; não antecipa o commit documental posterior. A identidade precisa do código avaliado continua nos SHA256 de `avaliacao/runs/test-v1/manifest.json`; commit não existia durante o experimento.

## Pendências concretas

1. SPTrans: obter token e validar cobertura/consulta real, separadamente da simulação.
2. Consolidar o commit documental mantendo identificada a revisão já implantada e validada. A operação Azure, inclusive alerta e recuperação, está concluída neste checkpoint; ambiente Railway da TBC permanece fora do escopo.
3. A nova entrega Cloud em AWS Sandbox e seu PDF final estão sob responsabilidade da frente Cloud, conforme orientação de Pedro após aceite relatado do professor. A Azure continua hospedando a IA; não há resultado AWS antecipado.
4. Pedro/integrante: conferir conteúdo e enviar links no Teams até 19/11/2026 às 23h55. Manter a URL Azure e os demais links disponíveis durante correção. Não houve submissão.

Nomes/RMs confirmados por Pedro: Filipe Prado Menezes RM98765; Cássio Eid Kobaysahi Yonetsuka RM99678; Pedro Henrique Salvitti Habiro RM88166. Nenhum nome ou RM foi inferido.

### Ajuste posterior ao experimento

A fronteira HTTP recebeu limite de corpo de 8 KiB, duas consultas simultâneas por processo e 10 s para envio do corpo. Isso evita fila ilimitada antes do slot LLM. Mudaram `app/main.py` e novo `app/limits.py`; Engine/LLM/recuperação/transit/settings/metrics e dados continuam com os hashes avaliados. O manifesto de avaliação original não foi reescrito para ocultar essa diferença. Testes 19/19 passaram. O smoke HTTP público posterior, registrado acima, validou a implantação que contém essa proteção.

Smoke da integração em Docker realizado por Cloud em `http://127.0.0.1:8002`: cinco checks passaram, resposta documental em 7,974 s e chegada em 4,705 s, em `evidencias/cloud/smoke-compose.json`. Essa evidência é local em containers e antecede o ajuste de admissão HTTP; a verificação pública posterior está separada em `evidencias/smoke-publico-ia.json`.

Desconexão durante o envio é tratada com resposta vazia499, sem inferência nem falso500 na telemetria. Teste da aplicação ASGI completa reproduziu e verificou a correção; contador de capacidade é liberado.
