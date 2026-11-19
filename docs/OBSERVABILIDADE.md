# Observabilidade do Ponto Certo

A stack local coleta a **mesma API publicada** e sonda sua URL de prontidão por HTTPS. Prometheus e Grafana locais são permitidos pela rubrica oficial (p.53). A configuração, isoladamente, **não comprova** coleta pública, dashboard preenchido nem alerta disparado. As evidências efetivas ficam em `evidencias/` e são relacionadas no status Cloud.

## Estado dos alvos e alcance das provas

No checkpoint de **19/11/2026 às 11:04:11 de São Paulo**, os alvos usavam a revisão `8b1e298`, com **Azure live** e **AWS demo**. A [promoção live](../evidencias/cloud/azure-live-deployment.json) reexecutou somente o job Azure com os mesmos digests; os [6/6 checks públicos separados](../evidencias/cloud/azure-live-public.json) comprovaram previsão SPTrans real, resposta vazia válida e descoberta de linhas. O [smoke genérico](../evidencias/cloud/azure-live-generic-smoke.json) manteve a chegada live sem execução; não é usado como prova dessa consulta. As métricas e o ensaio final AWS de 15 checks deste documento foram coletados em demo com LLM real. O ensaio Azure anterior também é histórico demo; a promoção live não altera o modo nem a data dessas evidências.

A [flag de deploy AWS está desabilitada e as três credenciais STS foram removidas do GitHub](../evidencias/cloud/live-promotion-config.json), preservando a revisão validada até o fim da sessão. Isso não desliga a EC2 nem encerra a coleta; Azure e seu monitor continuam independentes.

O checkpoint das evidências AWS fica fixado em `8b1e298`; revisões documentais posteriores da Azure têm seu próprio SHA. A revisão atual de `/healthz` da Azure pode avançar sem alterar a referência histórica dos testes ou o checkpoint AWS.

A [jornada pública live pelo navegador](../evidencias/jornada-publica-live.json) foi concluída em **19/11/2026 às 11:06:33 de São Paulo**, com identidade/revisão conferida às **11:06:52**: descoberta de quatro opções de linhas, seleção de 14 paradas retornadas e previsão real para a opção escolhida. As cinco capturas, horários e hashes constam do registro; a [tela final](../evidencias/interface-publica-live-chegada.jpg) mostra fonte e atualização sem aviso demo. A previsão é observação histórica da consulta, não horário atual nem garantia de chegada.

Documento de entrega: [Ponto-Certo-Deploy-Blindado.pdf](https://github.com/Salvittis/ponto-certo/releases/download/entrega-cloud-2026-11-19/Ponto-Certo-Deploy-Blindado.pdf), na [release entrega-cloud-2026-11-19](https://github.com/Salvittis/ponto-certo/releases/tag/entrega-cloud-2026-11-19). O PDF reúne arquitetura, evidências, custos e links de reprodução. A publicação do documento não representa submissão acadêmica; o envio fica com Pedro/equipe.

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
APP_HOST_PORT=8002 docker compose -f compose.yaml up -d
python3 observability/configure.py --url http://host.docker.internal:8002 --allow-local-http
docker compose -f compose.monitoring.yaml up -d
```

O Compose usa `8000` por padrão; o exemplo define `APP_HOST_PORT=8002` para evitar conflito com uma API nativa na porta 8000. Se usar a porta padrão, configure o target com `:8000`. `host.docker.internal` é resolvido pelo Docker Desktop. Em Linux, acrescente o mapeamento `host-gateway` conforme sua instalação. Antes de coletar evidências Cloud, reconfigure a URL pública e confirme que os targets não contêm localhost nem `host.docker.internal`.

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

### Limitação histórica da primeira falha e correção comprovada

No ensaio AWS da revisão `60aeedd`, em **19/11/2026**, a [pergunta pública retornou HTTP 503](../evidencias/aws/public-controlled-unavailable.json), mas os snapshots de [disparo](../evidencias/aws/observability-firing.json) e [recuperação](../evidencias/aws/observability-recovered.json) conservaram `error_rate_percent=0.0`. A consulta histórica ao contador confirmou a causa: a série rotulada de 503 surgiu já com valor **1**, sem amostra anterior em **0**. Como não havia incremento entre as amostras coletadas, `rate(...[5m])` resultou em zero. Nesse checkpoint, **0% no painel não comprova ausência de falhas HTTP**; o contrato HTTP e os alertas constituem evidências independentes. Os valores históricos permanecem intactos e o [ensaio de alerta/restauração mantém seus 12/12 checks aprovados](../evidencias/aws/alert-exercise.json).

A correção publicada na revisão `8b1e298a101eb9b90bf723efad268449381e2552` inicializa em zero as combinações conhecidas de status HTTP e resultados da LLM antes da primeira requisição. Também inclui recusas pelos limites anteriores ao roteamento na série fixa `route="/api/ask"`, sem usar caminhos arbitrários como labels. Testes em processo novo para a primeira resposta 503 e uma rejeição 413 passaram; a [tentativa 1 do pipeline](../evidencias/aws/hardened/security-passed-summary.json) aprovou 125/125 testes e os dois deploys. Inicializar séries conhecidas com zero segue a [recomendação oficial do Prometheus para métricas ausentes](https://prometheus.io/docs/practices/instrumentation/#avoid-missing-metrics). Para observar o primeiro incremento, a coleta precisa registrar o zero antes do evento.

A validação real no Prometheus AWS confirmou **0 → 1** nos contadores HTTP 503 e LLM indisponível: [antes, às 10:55:19 de São Paulo](../evidencias/aws/hardened/first-failure-before.json), e [depois, às 10:58:05](../evidencias/aws/hardened/first-failure-after.json), em 19/11/2026. A taxa HTTP de erro chegou a **11,1111% em cinco minutos**; a taxa específica 503 foi **0,00350877/s**. O [snapshot imediato ainda aguardando scrape](../evidencias/aws/hardened/first-failure-awaiting-scrape.json) permanece separado e não é a observação final. O [ensaio completo](../evidencias/aws/hardened/alert-exercise.json) passou **15/15 checks**, com dois alertas firing às 10:58:45 e [recuperação sem alertas ativos às 10:59:47](../evidencias/aws/hardened/observability-recovered.json). Na recuperação, a janela móvel ainda tinha **10,8168% de erros**; não foi zerada manualmente. A limitação histórica de `60aeedd` foi resolvida na nova publicação, sem modificar as evidências anteriores.

## Alertas e limiar

As regras estão em `observability/prometheus/alerts.yaml`:

- `PontoCertoPublicReadyUnavailable`: `probe_success == 0` continuamente por 1 minuto. Detecta prontidão HTTP indisponível e falhas DNS/TLS/rede.
- `PontoCertoModelNotReady`: `ponto_certo_model_ready == 0` por 1 minuto. Diferencia API viva de LLM não pronta.
- `PontoCertoMetricsUnavailable`: `up == 0` da API por 1 minuto. Detecta interrupção de telemetria, inclusive token incorreto, sem concluir sozinho que a aplicação caiu.

Uma falha isolada não dispara. A persistência de um minuto abrange múltiplas sondagens de 15 s, limita ruído de rede e detecta rapidamente a indisponibilidade de um MVP interativo. O disparo ocorre na primeira avaliação depois de o período ser satisfeito, então reserve cerca de 90 segundos no ensaio. O retorno da condição a falso resolve o alerta na avaliação seguinte.

## Coleta reproduzível e sanitizada

`scripts/collect-cloud-evidence.py` consulta as expressões diretamente do dashboard versionado. Registra os 16 resultados instantâneos e seu histórico de 5 minutos, em passos de 15 segundos, além de `up`, `probe_success`, prontidão do modelo, targets e alertas. Cada amostra de taxa/p95 considera seus próprios 5 minutos anteriores; saturação é instantânea. O SHA-256 do dashboard, os horários UTC, as expressões e as unidades acompanham os valores.

Deixe a coleta aquecer por pelo menos 5 minutos para o instantâneo e 10 minutos para um histórico completo de taxas. Depois de mudar de alvo local para público, aguarde 10 minutos: o coletor verifica as instâncias de `up` em toda essa janela ampliada e recusa atribuir métricas públicas se houver amostras de outro alvo. Isso evita misturar séries locais antigas nas taxas agregadas do dashboard. Execute o smoke público autorizado com inferência real para produzir tráfego. O coletor não gera perguntas, não provoca falhas e não reinicia serviços. Sem tráfego, p95 e percentual de erros podem ser nulos; isso não significa zero. Não ajuste nem preencha valores manualmente para aparentar sucesso.

```sh
PC_PUBLIC_URL='https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com'
PC_REVISION='SHA_COMPLETO_DA_REVISAO_PUBLICADA'
python3 scripts/collect-cloud-evidence.py \
  --public-url "$PC_PUBLIC_URL" --expect-revision "$PC_REVISION" \
  --azure-resource-group ponto-certo-fiap-rg --azure-vm ponto-certo-fiap-vm \
  --output evidencias/cloud/observability-baseline.json
```

Preencha `PC_REVISION` com o SHA completo esperado no deploy e verifique a correspondência com `/healthz`. Não use o HEAD local se houver commits ainda não publicados. As opções Azure são opcionais: criam um Managed Run Command que inspeciona os containers do projeto e verifica usuário, recursos e artefato do modelo. O registro contém digest/imagem, usuário efetivo, estado/saúde, limites, capabilities, política de reinício e portas. A seleção de campos do `docker inspect` exclui `Env`, logs, comandos de inicialização e mounts. A VM precisa da tag `project=ponto-certo`; o operador precisa das permissões de leitura da VM e de Managed Run Command descritas em `infra/OPERACAO.md`.

A coleta Azure também registra memória total/disponível do host por `/proc/meminfo`, CPU e memória/limite dos três serviços por `docker stats --no-stream`, e SHA-256/tamanho de `/models/qwen.gguf` na LLM. São retratos pontuais com horário, não um benchmark: CPU pode superar 100% em vários núcleos; a memória da CLI Docker desconta cache inativo no Linux e os valores formatados são arredondados. A amostra de recursos precede o cálculo do hash. Compare hash/tamanho coletados depois do reinício com os artefatos fixados no build; o coletor não faz o reinício. Ausência de medidas ou falha de leitura permanece explícita. A saída do guest é limitada a 3.800 bytes para não produzir JSON truncado pelo Run Command. [Semântica de `docker stats`](https://docs.docker.com/reference/cli/docker/container/stats/).

O coletor não lê nem envia `METRICS_TOKEN`: usa a API Prometheus em loopback, onde o scrape já está autenticado. Também verifica que `/metrics` público recusa acesso sem token. Só aceita origem HTTPS com DNS público, não segue redirects, remove labels fora de uma lista permitida e descarta annotations/textos de respostas. Ainda assim, revise o JSON e as capturas antes de publicar. A inspeção Azure é opcional e captura o estado no horário próprio registrado; não é atômica com o instantâneo Prometheus.

Use nomes diferentes para baseline, disparo e recuperação; sobrescrita exige `--overwrite`. Para uma captura rápida durante o alerta, omita as opções Azure:

```sh
python3 scripts/collect-cloud-evidence.py \
  --public-url "$PC_PUBLIC_URL" --expect-revision "$PC_REVISION" \
  --output evidencias/cloud/observability-firing.json
```

O código de saída `0` indica coleta concluída e targets/revisão compatíveis; não significa serviço saudável. `2` indica consulta incompleta, alvo/revisão incompatível ou falha de inspeção solicitada. Um alerta ativo ou um valor sem amostras continua sendo evidência válida. `metrics_complete` informa se os quatro valores são finitos; métricas de targets diferentes são anuladas. O objeto `metrics` usa os campos do manifesto (`latency_p95_seconds`, `traffic_requests_per_second`, `error_rate_percent`, `saturation_percent`, `scope`, `target`, `window`), mas o coletor não altera o manifesto e não marca checks como aprovados. Vincule cada resultado ao seu arquivo e preserve capturas do dashboard e das telas de alerta.

## Ensaio controlado e evidências reais

Execute em uma janela curta, após registrar a operação saudável e com o procedimento de restauração preparado. Para provar disponibilidade do MVP público, mantenha os targets apontando à **mesma URL pública** durante todo o ensaio. Não troque o alvo por uma URL inválida e não renomeie dados locais como públicos.

1. Registre horário/fuso, revisão de `/healthz`, URL, `probe_success=1`, `ponto_certo_model_ready=1` e um teste `/api/ask` com LLM real.
2. Interrompa temporariamente **o runtime da LLM da aplicação monitorada**, pelo controle operacional da infraestrutura escolhida. Preserve imagem, pesos e configuração. Não derrube o Prometheus; ele precisa observar a falha. O endpoint `/readyz` deve passar a 503 e perguntas devem receber indisponibilidade honesta. Se isso não ocorrer, corrija o contrato antes de afirmar o teste.
3. Aguarde aproximadamente 90 s e verifique o estado `firing` em [Alerts](http://127.0.0.1:9090/alerts). Guarde print com nome, estado, alvo e horário e execute o coletor com saída `observability-firing.json`, sem inspeção Azure para reduzir a duração da captura.
4. Restaure o runtime da LLM. Confirme `/readyz` 200, modelo pronto, teste real do assistente e alertas resolvidos. Capture a recuperação e preserve o intervalo histórico no dashboard.
5. Registre início/fim, ação exata, duração, resultados, commit e caminhos dos arquivos em `docs/STATUS-CLOUD.md` e no PDF.

Para ensaio **local**, a interrupção/restauração correspondentes são `docker compose -f compose.yaml stop llm` e `docker compose -f compose.yaml start llm`. Registre-o como local. Esses comandos locais não interrompem o serviço hospedado.

### Procedimento Azure com restauração preparada

Este procedimento interrompe a LLM pública por aproximadamente 120 segundos, além do tempo necessário para recarregar o modelo. Execute somente na janela operacional escolhida, sem deploy concorrente, depois de observar baseline saudável. Prometheus, API e proxy permanecem ativos. O lock impede que um deploy altere a release durante o ensaio; um timer no próprio host tenta restaurar a LLM em 180 segundos se o comando for interrompido. A restauração ainda depende de VM e Docker funcionando.

Prepare o script temporário na máquina do operador:

```sh
cat > /tmp/ponto-certo-alert-test.sh <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/ponto-certo
exec 9>/opt/ponto-certo/deploy.lock
flock -n 9
dc() { docker compose --env-file release.env -f compose.production.yaml "$@"; }
fallback="ponto-certo-alert-restore-$(date +%s)"
restore() {
  result=$?
  trap - EXIT
  if dc start llm >/dev/null; then
    systemctl stop "$fallback.timer" >/dev/null 2>&1 || true
    printf 'LLM start requested; verify public readiness and real inference.\n'
  else
    printf 'LLM restoration failed; emergency timer remains scheduled.\n' >&2
    result=1
  fi
  exit "$result"
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
systemd-run --unit="$fallback" --on-active=180s --collect \
  /usr/bin/flock --wait 60 /opt/ponto-certo/deploy.lock \
  /usr/bin/docker compose --project-directory /opt/ponto-certo \
  --env-file /opt/ponto-certo/release.env \
  -f /opt/ponto-certo/compose.production.yaml start llm >/dev/null
dc stop llm >/dev/null
printf 'LLM stopped; automatic start in 120 seconds.\n'
sleep 120
BASH
bash -n /tmp/ponto-certo-alert-test.sh
PC_ALERT_COMMAND="alert-test-$(date -u +%Y%m%dT%H%M%SZ)"
az vm run-command create \
  --resource-group ponto-certo-fiap-rg --vm-name ponto-certo-fiap-vm \
  --location chilecentral --run-command-name "$PC_ALERT_COMMAND" \
  --async-execution true --timeout-in-seconds 240 \
  --script "$(cat /tmp/ponto-certo-alert-test.sh)" \
  --only-show-errors --output none
```

Enquanto o comando assíncrono executa, observe os probes e capture o estado `firing` em torno de 90 segundos. Consulte a conclusão sem exportar o conteúdo dos parâmetros:

```sh
az vm run-command show \
  --resource-group ponto-certo-fiap-rg --vm-name ponto-certo-fiap-vm \
  --run-command-name "$PC_ALERT_COMMAND" --expand instanceView \
  --query 'instanceView.{state:executionState,exitCode:exitCode}' \
  --only-show-errors --output json
```

Depois da restauração, confirme `/readyz` 200, `ponto_certo_model_ready=1`, `probe_success=1`, ausência dos alertas ativos do ensaio e uma resposta real do smoke. Repita a coleta baseline com saída `evidencias/cloud/observability-recovered.json`. `start` solicitado ou comando Azure concluído não provam recuperação por si só. Guarde os horários efetivos e o nome do Run Command como trilha operacional.

Se a restauração automática falhar, use outro Managed Run Command para solicitar `start llm`, respeitando o mesmo lock, e investigue pelo acesso operacional privado:

```sh
az vm run-command create \
  --resource-group ponto-certo-fiap-rg --vm-name ponto-certo-fiap-vm \
  --location chilecentral --run-command-name "restore-llm-$(date -u +%Y%m%dT%H%M%SZ)" \
  --timeout-in-seconds 120 \
  --script 'set -eu; cd /opt/ponto-certo; exec 9>deploy.lock; flock -w 60 9; docker compose --env-file release.env -f compose.production.yaml start llm >/dev/null' \
  --only-show-errors --output none
```

Alternativa sem indisponibilizar a IA: interrompa apenas a autenticação da coleta por cerca de 90 s, mantendo a URL real. Isso deve disparar `PontoCertoMetricsUnavailable` enquanto `/readyz` segue saudável; restaure o mesmo segredo do servidor e confirme resolução. A evidência comprova um alerta real de **falha de telemetria**, não uma falha da LLM. Não mude o token SPTrans nem enfraqueça a proteção de `/metrics`.

Os comandos acima são procedimentos, não evidências de execução. Somente os arquivos coletados durante o ensaio e as capturas correspondentes comprovam o disparo e a recuperação.

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
- [API HTTP Prometheus: consultas instantâneas, séries, targets e alertas](https://prometheus.io/docs/prometheus/latest/querying/api/).
- [Provisionamento Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/).
- [Grafana em Docker e segredo por arquivo](https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/).
- [Configuração Blackbox Exporter](https://github.com/prometheus/blackbox_exporter/blob/master/CONFIGURATION.md).

Configuração preparada em 19/11/2026. Configuração e teste unitário não equivalem a validação pública; consultar o status Cloud para o que foi efetivamente realizado.
