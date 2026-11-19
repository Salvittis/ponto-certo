# Observabilidade do Ponto Certo

A stack local coleta a **mesma API publicada** e sonda sua URL de prontidão por HTTPS. Prometheus e Grafana locais são permitidos pela rubrica oficial (p.53). A configuração, isoladamente, **não comprova** coleta pública, dashboard preenchido nem alerta disparado. As evidências efetivas ficam em `evidencias/` e são relacionadas no status Cloud.

## Componentes e limites

- Prometheus 3.16.0: scrape e regras a cada 15 segundos; retenção máxima de 10 dias ou 512 MB, o que ocorrer primeiro.
- Grafana 13.3.1: datasource e dashboard provisionados automaticamente; fuso `America/Sao_Paulo`; janela inicial de 30 minutos.
- Blackbox Exporter 0.29.1: `GET /readyz` público, timeout de 8 segundos, HTTP 200 obrigatório, TLS validado, sem seguir redirects.
- Somente `127.0.0.1:9090` e `127.0.0.1:3001` são publicadas no computador do operador. Blackbox não publica porta. Não exponha essas portas com túnel, proxy ou regra de firewall pública.
- `/metrics` exige o mesmo Bearer `METRICS_TOKEN` configurado na API. O token é enviado em cabeçalho, não em URL. `/readyz` é público e não retorna segredos.
- Prometheus decide e registra o estado dos alertas. Não há serviço externo de notificação; um alerta `firing` é visível na interface e API do Prometheus. Não afirmar recebimento de e-mail/WhatsApp.
- O computador/Docker precisam permanecer ativos para a coleta continuar. A aplicação em nuvem continua independente, mas parar esta stack interrompe a observabilidade. Volumes preservam amostras e Grafana entre reinícios.

## Configurar e executar

Pré-requisitos: Python 3, Docker com Compose, URL pública HTTPS e token já configurado na API. Nunca use um token SPTrans no lugar do token de métricas.

```sh
python3 observability/configure.py --url https://URL-PUBLICA-DO-MVP
# O prompt recebe METRICS_TOKEN sem exibi-lo.
docker compose -f compose.monitoring.yaml config --quiet
docker compose -f compose.monitoring.yaml up -d
```

O script também aceita `--metrics-token-file /caminho/local/arquivo`, ou `METRICS_TOKEN` no ambiente do processo, sem imprimir o valor. Não passe o segredo como argumento. Ele cria `.runtime/monitoring/`, com permissão 0700, e arquivos read-only para montagem individual em containers não root. Essa pasta permanece fora do Git/imagem. A senha Grafana é aleatória e preservada em reexecuções.

Abra [Grafana local](http://127.0.0.1:3001/d/ponto-certo-golden-signals) e entre com usuário `admin`; obtenha a senha diretamente do arquivo local `.runtime/monitoring/grafana-admin-password`. Não inclua esse arquivo, o token nem a tela de login preenchida em evidências. A senha inicial só é aplicada ao criar o volume Grafana; para mudar uma senha existente, use o fluxo de alteração de senha da instalação.

Abra [Targets](http://127.0.0.1:9090/targets) e confirme as duas coletas. O alvo `ponto-certo-api` é `https://<host>/metrics`; o alvo `ponto-certo-ready` representa o probe da URL pública `https://<host>/readyz`. O Bearer não aparece nos arquivos de targets.

Após alterar a URL ou token, execute novamente o configurador e recrie os serviços para remontar os arquivos:

```sh
docker compose -f compose.monitoring.yaml up -d --force-recreate
```

Para integração **local**, sem valor de prova de publicação, use:

```sh
python3 observability/configure.py --url http://host.docker.internal:8000 --allow-local-http
docker compose -f compose.monitoring.yaml up -d
```

`host.docker.internal` é resolvido pelo Docker Desktop. Em Linux, acrescente o mapeamento `host-gateway` conforme sua instalação. Antes de coletar evidências Cloud, reconfigure a URL pública e confirme que os targets não contêm localhost nem `host.docker.internal`.

## Quatro métricas de ouro

Todas as consultas usam `job="ponto-certo-api"`. As métricas da jornada filtram `route="/api/ask"`, excluindo probes e arquivos estáticos.

| Sinal | Métrica e consulta | Unidade e interpretação |
|---|---|---|
| Latência | `histogram_quantile(0.95, sum by (le) (rate(ponto_certo_http_request_duration_seconds_bucket{route="/api/ask"}[5m])))`; mesmo cálculo para `ponto_certo_llm_duration_seconds_bucket` | Segundos, p95 em janela móvel de 5 min. Aproximação por buckets; a latência da LLM inclui espera pelo semáforo. Sem amostras o painel pode ficar sem valor, não representa latência zero. |
| Tráfego | `sum(rate(ponto_certo_http_requests_total{route="/api/ask"}[5m]))`; `sum(rate(ponto_certo_llm_requests_total[5m]))` | Perguntas/s e inferências/s, janela 5 min. Clarificações e recusas podem não chamar LLM. |
| Erros | Taxa de HTTP `status=~"5.."` dividida pela taxa total de `/api/ask`; chamadas LLM com `outcome!="ok"` divididas pelo total | Percentual em 5 min. Erros LLM incluem indisponibilidade e JSON inválido. `not_found` e `clarification` são resultados funcionais, não erros. O numerador é zero quando há tráfego observado sem erros; sem tráfego, não há percentual significativo. |
| Saturação | `100 * ponto_certo_llm_inflight / ponto_certo_llm_capacity` | Percentual instantâneo de slots ocupados. Capacidade atual: 1. 100% significa slot em uso, não CPU em 100%. Correlação com latência e HTTP em voo revela fila/pressão. |

Painéis complementares: `ponto_certo_model_ready`, `up`, `probe_success`, `ALERTS`, `ponto_certo_http_inflight`, `ponto_certo_answers_total` por status e `process_resident_memory_bytes`. O RSS é **apenas do processo Python da API**, não inclui processo/pesos da LLM. A sondagem de prontidão não faz uma inferência; os testes externos com modelo real complementam esse sinal.

A amostragem a cada 15 segundos pode perder picos curtos de saturação. Para a evidência, gere perguntas reais sequenciais pelo smoke/teste autorizado e preserve a janela histórica; não invente séries nem apresente um gráfico vazio como prova. Dados de transporte em modo `demo` continuam identificados como sintéticos; a latência e os erros medidos no serviço são operação real.

## Alertas e limiar

As regras estão em `observability/prometheus/alerts.yaml`:

- `PontoCertoPublicReadyUnavailable`: `probe_success == 0` continuamente por 1 minuto. Detecta prontidão HTTP indisponível e falhas DNS/TLS/rede.
- `PontoCertoModelNotReady`: `ponto_certo_model_ready == 0` por 1 minuto. Diferencia API viva de LLM não pronta.
- `PontoCertoMetricsUnavailable`: `up == 0` da API por 1 minuto. Detecta interrupção de telemetria, inclusive token incorreto, sem concluir sozinho que a aplicação caiu.

Uma falha isolada não dispara. A persistência de um minuto abrange múltiplas sondagens de 15 s, limita ruído de rede e detecta rapidamente a indisponibilidade de um MVP interativo. O disparo ocorre na primeira avaliação depois de o período ser satisfeito, então reserve cerca de 90 segundos no ensaio. O retorno da condição a falso resolve o alerta na avaliação seguinte.

## Ensaio controlado e evidências reais

Execute em uma janela curta, após registrar a operação saudável e com o procedimento de restauração preparado. Para provar disponibilidade do MVP público, mantenha os targets apontando à **mesma URL pública** durante todo o ensaio. Não troque o alvo por uma URL inválida e não renomeie dados locais como públicos.

1. Registre horário/fuso, revisão de `/healthz`, URL, `probe_success=1`, `ponto_certo_model_ready=1` e um teste `/api/ask` com LLM real.
2. Interrompa temporariamente **o runtime da LLM da aplicação monitorada**, pelo controle operacional da infraestrutura escolhida. Preserve imagem, pesos e configuração. Não derrube o Prometheus; ele precisa observar a falha. O endpoint `/readyz` deve passar a 503 e perguntas devem receber indisponibilidade honesta. Se isso não ocorrer, corrija o contrato antes de afirmar o teste.
3. Aguarde aproximadamente 90 s e verifique o estado `firing` em [Alerts](http://127.0.0.1:9090/alerts). Guarde print com nome, estado, alvo e horário e o JSON de `GET /api/v1/alerts`. O JSON não contém token e deve ser inspecionado antes de publicar.
4. Restaure o runtime da LLM. Confirme `/readyz` 200, modelo pronto, teste real do assistente e alertas resolvidos. Capture a recuperação e preserve o intervalo histórico no dashboard.
5. Registre início/fim, ação exata, duração, resultados, commit e caminhos dos arquivos em `docs/STATUS-CLOUD.md` e no PDF.

Para ensaio **local**, a interrupção/restauração correspondentes são `docker compose -f compose.yaml stop llm` e `docker compose -f compose.yaml start llm`. Registre-o como local. Para a nuvem, use o mecanismo real do provedor e registre o comando/ação efetivamente executado; esses comandos locais não interrompem o serviço hospedado.

Alternativa sem indisponibilizar a IA: interrompa apenas a autenticação da coleta por cerca de 90 s, mantendo a URL real. Isso deve disparar `PontoCertoMetricsUnavailable` enquanto `/readyz` segue saudável; restaure o mesmo segredo do servidor e confirme resolução. A evidência comprova um alerta real de **falha de telemetria**, não uma falha da LLM. Não mude o token SPTrans nem enfraqueça a proteção de `/metrics`.

Exportação sanitizada do estado de alertas, sem credenciais:

```sh
curl --fail --silent http://127.0.0.1:9090/api/v1/alerts > evidencias/cloud-alertas.json
```

## Validação da configuração

```sh
docker run --rm --entrypoint promtool \
  -v "$PWD/observability/prometheus:/etc/prometheus:ro" \
  prom/prometheus:v3.16.0 check rules /etc/prometheus/alerts.yaml
docker run --rm --entrypoint promtool \
  -v "$PWD/observability/prometheus:/etc/prometheus:ro" \
  prom/prometheus:v3.16.0 test rules /etc/prometheus/alerts.test.yaml
python3 -m json.tool observability/grafana/dashboards/ponto-certo.json > /dev/null
docker compose -f compose.monitoring.yaml exec prometheus \
  promtool check config /etc/prometheus/prometheus.yaml
```

Os testes de regra usam séries **sintéticas identificadas**, verificam tempo para disparo e recuperação e não substituem o ensaio com serviço real. Validar JSON não prova que um dashboard renderiza ou contém amostras; a revisão visual e a coleta real são necessárias.

Para parar a stack local preservando dados: `docker compose -f compose.monitoring.yaml down`. Não use `down -v` durante a janela de correção, pois remove o histórico. Caso o operador pare Docker/computador, registre a lacuna e retome a coleta ao ligar.

## Referências técnicas

- [Configuração do Prometheus: autorização e file discovery](https://prometheus.io/docs/prometheus/latest/configuration/configuration/).
- [Regras de alerta Prometheus](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).
- [Provisionamento Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/).
- [Grafana em Docker e segredo por arquivo](https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/).
- [Configuração Blackbox Exporter](https://github.com/prometheus/blackbox_exporter/blob/master/CONFIGURATION.md).

Configuração preparada em 19/11/2026. Configuração e teste unitário não equivalem a validação pública; consultar o status Cloud para o que foi efetivamente realizado.
