# Estado da IA — Ponto Certo 0.1.0

Atualizado em 19/11/2026. Estado parcial da entrega global: aplicação e avaliação locais executadas; publicação e integração pública dependem da frente Cloud. Submissão acadêmica não realizada.

## Funciona e foi executado

- Mesma aplicação em `ponto-certo/`: FastAPI, frontend HTML/CSS/JS, LLM **local** Qwen2.5-1.5B Q4_K_M no llama.cpp b12464, recuperação TF-IDF e agente de ferramentas restritas.
- Interface → API → recuperação/ferramenta → modelo real → resposta: verificada no navegador em consulta documental, chegada sintética e esclarecimento. Capturas desktop e viewport móvel 390×844 em `evidencias/interface-*.jpg`. Avaliação visual manual, sem auditoria completa WCAG ou usuário com leitor de tela.
- Smoke HTTP real passou em `http://127.0.0.1:8000`, cobrindo saúde, prontidão, configuração, documental e chegada; `evidencias/smoke-local.json` preserva data/hora e checks.
- 16 testes automatizados API passaram: validação, não exposição de tokens/entrada inválida, métricas Bearer, saúde/prontidão separadas, falha de modelo e assets. Usam modelo falso isolado; **não** são apresentados como inferência real.
- Modelo GGUF SHA256 verificado. Carregamento local observado 9,477 s; RSS instantâneo 1.106.160 KiB (~1,05 GiB), Mac Apple M4/16GB. Não extrapolar para Cloud CPU; `evidencias/modelo-local.json` distingue observação e estimativa.
- Base: 18 trechos com fonte/data/condições de uso. Recall@1=13/14 (92,86%), recall@3=14/14 (100%); limiar 0,05 calibrado em DEV. Negativas 4/4 rejeitadas; corpus e amostra pequenos.
- Avaliação real: DEV6 + TEST24, cada qual três configurações com mesmos pesos/parâmetros. Saídas brutas, finais, hashes e condições em `avaliacao/runs/{dev-v1,test-v1}`. TEST foi reservado antes das saídas e não usado para ajustar implementação.

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

Pedro confirmou ausência de token e autorizou simulação. Fixture sintética versionada em `dados/fixtures/sptrans-demo.json`: 8000-10, códigos 1273/34041, ponto demonstrativo4200153, relógio19/11/2026 10:00. Não é captura externa e não comprova operação/itinerário atual. Cenários normal, vazio, antigo e falha. Nenhuma previsão histórica foi indexada como atual.

Cliente live implementado com endpoints fixos, HTTPS, token só no servidor e verificação temporal. **Não validado contra SPTrans real.** Para concluir, obter chave na área oficial, configurar `SPTRANS_TOKEN` em segredo e `DATA_MODE=live`, descobrir linhas/pontos realmente retornados e registrar consulta sanitizada com `python -m scripts.capture_live --line CODIGO --stop CODIGO`. Não usar IDs demo como cobertura presumida.

## Contrato e versão para Cloud

Contrato v0.1.0 em `docs/CONTRATO-IA-CLOUD.md`, enviado ao agente Cloud; primeira versão executável comunicada em19/11/2026. Mesmos modelo/runtime alinhados, dependências runtime fixadas, portas8000/8081, health/readiness/config/metrics e smoke disponíveis. Cloud possui Docker/Compose, CI/CD, Terraform e observabilidade; não foram alterados por IA.

Repositório único: https://github.com/Salvittis/ponto-certo (remoto criado por Cloud; primeiro commit/publicação ainda em coordenação). Identidade precisa do código avaliado consta dos SHA256 em `avaliacao/runs/test-v1/manifest.json`; commit não existia durante o experimento. APP_VERSION=0.1.0 e APP_REVISION devem identificar o deploy.

## Pendências concretas

1. Cloud: confirmar commit público, validar containers/modelo e jornada na URL pública. Ambiente Railway da TBC foi excluído do escopo a pedido de Pedro; conta pessoal/custo zero em definição pela outra frente. Não há URL pública validada neste registro.
2. SPTrans: obter token e validar cobertura/consulta real, separadamente da simulação.
3. Confirmar publicação do relatório, notebook com saídas e vídeo demonstrativo junto ao primeiro push. Artefatos locais não equivalem a link público funcional.
4. Pedro/integrante: conferir conteúdo e enviar links no Teams até19/11/2026 23h55. Manter links disponíveis durante correção. Não houve submissão.

Nomes/RMs confirmados por Pedro: Filipe Prado Menezes RM98765; Cássio Eid Kobaysahi Yonetsuka RM99678; Pedro Henrique Salvitti Habiro RM88166. Nenhum nome ou RM foi inferido.
