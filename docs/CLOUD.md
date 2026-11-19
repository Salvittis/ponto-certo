# Ficha Técnica - Ponto Certo / Deploy Blindado

| Campo | Definição |
|---|---|
| Produto | Ponto Certo, assistente de informação sobre ônibus municipais de São Paulo |
| Cidadão e problema | Pessoas que dependem do ônibus e precisam de informação confiável sobre linhas e espera |
| Proposta | Explicar informações com fontes, atualização e distinção entre ausência de informação, dúvida e falha |
| Disciplina | Secure DevOps Tools & Cloud Computing, Global Solution CitizenTech 2026.2, FIAP |
| Responsável IA e Cloud | Pedro Henrique Salvitti Habiro |
| Arquitetura | HTTPS/Caddy → FastAPI → recuperação documental e consultas controladas → Qwen local; SPTrans no modo live |
| Modelo de IA | Qwen2.5-1.5B-Instruct GGUF Q4_K_M, revisão `91cad51170dc346986eccefdc2dd33a9da36ead9`; execução própria com llama.cpp b12464 |
| Repositório | [Salvittis/ponto-certo](https://github.com/Salvittis/ponto-certo) |
| MVP público da IA | **AZURE OPERACIONAL**, incluindo alerta e recuperação em 19/11/2026, modo demo. [Abrir Ponto Certo](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) |
| Entrega Cloud | AWS Academy Sandbox solicitada após aceite do professor relatado por Pedro; execução e PDF final ainda pendentes neste checkpoint |
| Dados | Demonstração sintética; integração real SPTrans depende de token e validação |
| Indicadores de impacto | Acerto, respostas sem suporte, cobertura e atualidade da informação; posteriormente, compreensão e incerteza percebida. Redução da espera não foi medida |
| Contribuição proposta | ODS 11, informação para mobilidade urbana; redução de espera não foi medida |

| Integrante | RM |
|---|---|
| Filipe Prado Menezes | RM98765 |
| Cássio Eid Kobaysahi Yonetsuka | RM99678 |
| Pedro Henrique Salvitti Habiro | RM88166 |

**Revisão documental:** 1.2.0, 19/11/2026. Nomes e RMs conferidos com a Ficha Técnica do [README](../README.md). Este documento explica a configuração; o [estado operacional](STATUS-CLOUD.md) e o manifesto de evidências registram o que foi realmente executado. A geração do PDF não realiza deploy nem transforma uma preparação em resultado validado.

## Escopo e leitura das evidências

Cloud publica a **mesma aplicação e o mesmo modelo** da frente IA. A API usa FastAPI. O modelo é Qwen2.5-1.5B-Instruct Q4_K_M, executado por llama.cpp b12464. A base documental, o protocolo de avaliação e os dados de demonstração permanecem os do repositório. Não há API comercial de LLM. Maker, RPA e visão computacional previstos pela equipe não são declarados como implementados nesta frente.

A infraestrutura usa Azure for Students, separada de qualquer conta corporativa. A ativação acadêmica foi confirmada pelo operador em 19/11/2026: US$100 de crédito, validade até 19/11/2027 e spending limit ativo. **Provisionamento CONCLUÍDO**: 12 recursos criados, nenhuma alteração/destruição, em `chilecentral` (Chile), com VM B2als_v2. Leitura posterior da API confirmou VM, NSG e IP em `Succeeded`; a [evidência sanitizada](../evidencias/cloud/terraform-applied.json) preserva configuração e limites. Hostname: [ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com). **Publicação VALIDADA** no commit `48752d037ee6b7feaee1806ab00dc60e465ad745`: [run 44521584358](https://github.com/Salvittis/ponto-certo/actions/runs/44521584358) com oito jobs e 54 testes aprovados; [smoke público](../evidencias/cloud/smoke-public-first.json) com cinco checks HTTPS passando e inferência real. A [leitura de saúde/prontidão](../evidencias/cloud/public-first-ready.json) confirma a revisão publicada e o modo demo; os [contratos públicos](../evidencias/cloud/public-failure-contracts.json) confirmam esclarecimento, ausência de linha e entrada inválida. A [captura da interface](../evidencias/cloud/screenshots/public-app.jpg) mostra a aplicação publicada. O [baseline público](../evidencias/cloud/observability-baseline.json) também comprova UIDs efetivos, SHA/tamanho dos pesos e as quatro métricas. O [dashboard](../evidencias/cloud/screenshots/dashboard.jpg), [ensaio de alerta](../evidencias/cloud/alert-exercise.json), [stop/start da LLM](../evidencias/cloud/restart-public.json) e [smoke após recuperação](../evidencias/cloud/smoke-public-recovered.json) também foram verificados. Os nove checks Azure estão aprovados; a etapa Azure está operacionalmente concluída. O PDF final Cloud aguarda a nova fase AWS.

**Nova orientação de entrega:** Pedro relatou em 19/11/2026 que o professor aceitou AWS Academy Sandbox e pediu a entrega Cloud nessa plataforma. A decisão inicial de evitar o Sandbox por remover recursos ao fim da sessão foi revista; essa limitação continua registrada. **Azure permanece ativa para a IA; AWS será o ambiente demonstrado na entrega final Cloud.** Neste checkpoint, AWS ainda não tem execução validada. O aceite é relato de Pedro, não uma regra inventada a partir do PDF. Provas Azure e AWS serão identificadas separadamente, sem atribuir uma implantação à outra. Histórico e fonte do laboratório: [STATUS-CLOUD.md](STATUS-CLOUD.md).

Este documento consolida a **fase Azure validada** e a nova direção da entrega Cloud. O manifesto atual `evidencias/cloud/manifest.json` identifica `provider: azure` e hospedagem persistente da IA. A geração do PDF final fica pendente até incorporar configuração, custos, URLs, manifesto e evidências efetivas da AWS. Campos ausentes permanecem PENDENTE. Evidência local ou Azure não será renomeada como AWS; os nove checks Azure não comprovam a implantação no Sandbox.

## Arquitetura Azure validada e limites de rede

```mermaid
flowchart TB
    U[Cidadão / navegador] -->|HTTPS 443| C
    G[GitHub Actions: scanners, build e testes] -->|imagens aprovadas por digest| R[GHCR / acesso conforme pacote]
    G -->|OIDC / Managed Run Command| V
    subgraph V[Azure VM provisionada: Ubuntu 24.04 / 2 vCPU / 4 GiB]
      C[Caddy não root: 80/443] -->|rede frontend| A[FastAPI não root: 8000]
      A -->|rede backend privada| L[llama.cpp não root: 8081 / Qwen 1,5B]
      A --> B[Base documental + fixtures sintéticas]
    end
    R -->|pull aprovado| V
    A -. modo live .-> S[API SPTrans / HTTPS]
    P[Prometheus + Grafana no computador do operador] -->|HTTPS /metrics + Bearer| C
    P -->|HTTPS /readyz sem segredo| C
```

A NSG permite somente TCP 80 e 443 de entrada; uma regra seguinte nega as demais portas, inclusive 22. A chave pública administrativa é requisito do recurso VM, sem abertura de SSH. Não há RDP, Docker socket ou porta do modelo expostos. App e LLM não publicam suas portas no host; Caddy atende as portas externas usando portas internas altas e usuário 10001. A rede backend é interna ao Compose. A app possui saída para fontes necessárias; não há controle restritivo de egress neste MVP.

Trata-se de uma VM única, sem alta disponibilidade nem balanceamento. Os 2 vCPUs são compartilhados entre host e containers; os limites individuais não reservam capacidade. B2als_v2 é burstable e pode reduzir desempenho quando os créditos de CPU acabarem. Medições do Mac com Metal não antecipam desempenho da VM x64 com CPU.

## Containerização e contrato IA

Os [Dockerfiles](../Dockerfile) e [modelo](../Dockerfile.llm) fixam bases por digest, executam como UID/GID 10001 e não copiam `.env`, state ou credenciais. O modelo GGUF tem revisão e SHA-256 verificados no build. Pesos ficam na imagem, evitando download após cada reinício. A tag de commit identifica a versão; o deploy usa o digest do conteúdo aprovado.

O [Compose local](../compose.yaml) publica apenas `127.0.0.1:8000`; o [Compose de produção](../compose.production.yaml) acrescenta Caddy/TLS. Os containers usam filesystem somente leitura, tmpfs limitado, `cap_drop: ALL`, `no-new-privileges`, limites de CPU/RAM e reinício `unless-stopped`. Produção: LLM até 3 GiB, app 512 MiB e proxy 128 MiB; a margem restante inclui sistema operacional e Docker; o snapshot de memória está registrado abaixo. Certificados Caddy persistem em diretórios de propriedade do UID do proxy.

A leitura pública de 19/11/2026 entre **12:26:30 e 12:26:34 UTC**, preservada no [baseline](../evidencias/cloud/observability-baseline.json), observou app, LLM e proxy `running/healthy`, UID efetivo **10001**, filesystem somente leitura, `cap_drop: ALL` e `no-new-privileges`. App e LLM não tinham portas publicadas no host. `/models/qwen.gguf` apresentou **1.117.320.736 bytes** e SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`, iguais ao artefato fixado. O [stop/start real da LLM](../evidencias/cloud/restart-public.json), concluído depois, confirmou o mesmo hash/tamanho e imagens, seguido de inferência válida. O teste não incluiu reboot da VM nem reinício do proxy.

O host registrou **4.043.804.672 bytes** de memória total e **2.502.082.560 bytes disponíveis** segundo `/proc/meminfo`. Sob inferência, `docker stats --no-stream` reportou para a LLM **968.255.078 bytes (~968,3 MB)** e **193,65% de CPU**, com limite de 3 GiB. CPU pode ultrapassar 100% ao usar mais de um núcleo; a memória informada pelo Docker no Linux desconta cache inativo e parte de unidades arredondadas. Host, containers e hash foram coletados sequencialmente, com recursos medidos antes do hash: é um snapshot, não um benchmark de capacidade nem garantia de disponibilidade futura.

`/healthz` verifica processo e revisão; `/readyz` verifica prontidão essencial; `/metrics` exige Bearer. O healthcheck do processo não substitui teste real de inferência. O contrato completo está em [CONTRATO-IA-CLOUD.md](CONTRATO-IA-CLOUD.md). Perguntas de demonstração usam cenários sintéticos claramente identificados. Em falha real, a interface deve informar indisponibilidade, sem simular sucesso.

## Terraform, identidade e state

[infra/OPERACAO.md](../infra/OPERACAO.md) é a referência operacional detalhada. Terraform provisiona RG dedicado, VNet/subnet, NSG, NIC, IP Standard/DNS, VM Ubuntu 24.04 com imagem de versão numérica fixa, SSD 32 GiB e identidade de deploy. Provider AzureRM 5.14.0 e checksums estão fixados no lockfile. Cloud-init instala Docker/Compose pelo repositório oficial, prepara diretórios e rotação de logs; não contém segredos.

O state fica fora do checkout em `$HOME/.local/share/ponto-certo/terraform/terraform.tfstate`, via `bash infra/tf.sh`. Pasta 700, arquivos 600 por `umask 077`, backend com lock local e um único operador. FileVault foi verificado ativo; backup pós-apply em 600 foi comparado por SHA-256 com o state, no **mesmo disco FileVault**, fora do checkout. Não é backup offsite e não protege contra perda do computador. `sensitive` no Terraform **não cifra** state. `.tfvars`, planos, chaves privadas, cache e state não entram no Git nem em artefatos de Actions.

A identidade gerenciada de CI não é anexada à VM. Federação OIDC confia no prefixo imutável confirmado pela API GitHub, `repo:Salvittis@82597471/ponto-certo@1464046587`, seguido de `:environment:production`. Os IDs identificam proprietário/repositório e são obtidos pela API na reprodução; o formato legado sem IDs foi rejeitado pelo Azure com `AADSTS700213`. A variável obrigatória `github_oidc_subject_prefix` valida formato e correspondência com `github_repository`. A regra do environment deve permitir somente `main`, porque o subject com environment não inclui branch. RBAC dá leitura de VM/instanceView e read/write/delete de Managed Run Commands, atribuído apenas à VM. Não permite criar rede, VM ou permissões. Executar comando continua sendo poder administrativo sobre esse host.

A correção OIDC já foi aplicada pelo Terraform com 0 criações, 1 atualização e 0 destruições, restrita à credencial federada. Na tentativa 2 do run 44517488349, a autenticação Azure passou, mas a validação pública falhou às 12:08:25 UTC de 19/11: `Caddyfile` criado com modo 600 pelo administrador não podia ser lido pelo proxy UID 10001. A recuperação interrompeu a primeira release, sem antecessora saudável. A correção de permissão e a regressão foram publicadas no commit `48752d037ee6b7feaee1806ab00dc60e465ad745`; o novo pipeline/deploy passou e o smoke HTTPS comprovou a aplicação operacional. A proteção de `runtime.env` em modo 600 foi preservada. [Estado Cloud](STATUS-CLOUD.md), [correção OIDC](../evidencias/cloud/oidc-correction.json) e [smoke externo](../evidencias/cloud/smoke-public-before-proxy-fix.json) distinguem essas etapas.

`METRICS_TOKEN` e, no modo live, `SPTRANS_TOKEN` são enviados em `protectedParameters`, por JSON temporário 600. O script não imprime o payload. Na VM, `/opt/ponto-certo/runtime.env` é 600 e `/opt/ponto-certo` é 700. OIDC usa credencial curta, sem secret duradouro Azure. Para pull de pacotes GHCR privados, o fluxo de deploy usa `GITHUB_TOKEN` efêmero com `packages: read`, enviado como parâmetro protegido para login Docker temporário e removido ao final. Esse token não pertence ao arquivo de runtime. Não publicar tokens, `.env`, parâmetros protegidos ou state em capturas.

## Pipeline e bloqueio verificável

[devsecops.yml](../.github/workflows/devsecops.yml) executa em cada push, pull request e disparo manual. Os jobs verificam Gitleaks (histórico), Semgrep (política local), testes de regressão, build de app/LLM e Trivy nas imagens app, modelo e proxy. HIGH/CRITICAL e achados de segredo barram as imagens. Versões e ações estão fixadas; exceções futuras precisam de justificativa revisada.

Publicação depende de todos os gates. Em push na `main`, o job publica **os mesmos arquivos de imagem já examinados**, sem rebuild, resolve os digests de app, LLM e proxy e libera deploy. Não se presume que pacotes GHCR sejam públicos; o código-fonte público permite reprodução por build. O environment `production` autentica por OIDC; [deploy-azure.py](../scripts/deploy-azure.py) só aceita refs GHCR por digest e uma VM marcada como Ponto Certo. [release.sh](../deploy/release.sh) espera cloud-init, serializa releases, aplica Compose e tenta restaurar a configuração anterior se a operação ou validação pública falhar. Primeira instalação não possui versão anterior: a recuperação interrompe a release defeituosa. O job verifica HTTPS, revisão, prontidão e smoke com modelo real; o manifesto registra o resultado efetivo.

Para demonstrar o bloqueio, [security-demo.py](../scripts/security-demo.py) cria uma função sintética com `eval`, nunca importada ou executada. A sequência de evidência requer commit com achado, execução barrada e deploy ausente, correção e nova execução da **mesma política** aprovada. Gitleaks não deve receber segredo real para esse ensaio. Remover scanner, baixar severidade ou usar `continue-on-error` não é correção. O bloqueio foi observado no [run 44515603367](https://github.com/Salvittis/ponto-certo/actions/runs/44515603367); a execução final aprovada está em [pipeline-passed.json](../evidencias/cloud/pipeline-passed.json) e [security-passed-summary.json](../evidencias/cloud/security-passed-summary.json), com scanners, testes, digests publicados e deploy do mesmo commit. Zero achados vale para a política, versões e bases registradas, sem afirmar ausência de toda vulnerabilidade.

## Métricas, alerta e recuperação

[OBSERVABILIDADE.md](OBSERVABILIDADE.md) define a stack local Prometheus/Grafana, permitida pela rubrica p.53, ativa e apontada à mesma URL pública. App e LLM locais estão paradas; a inferência pública executa na VM Azure. A coleta dos quatro valores, a [captura do dashboard](../evidencias/cloud/screenshots/dashboard.jpg), o alerta e a recuperação foram comprovados contra a Azure. Isso não representa monitoramento AWS, ainda pendente. Grafana e Prometheus escutam só em loopback; o modelo permanece privado. O computador do operador precisa estar ativo para a coleta continuar.

| Sinal | Definição e unidade | Limite de interpretação |
|---|---|---|
| Latência | p95 do histograma HTTP `/api/ask`, janela 5 min, segundos | Aproximação por buckets; não inferir zero sem amostras |
| Tráfego | `rate(ponto_certo_http_requests_total[5m])` filtrada por `/api/ask`, perguntas/s | Probes e arquivos estáticos ficam fora da jornada |
| Erros | Taxa HTTP 5xx / taxa total de perguntas, em % | `not_found` e `clarification` não são erros de infraestrutura |
| Saturação | `100 * ponto_certo_llm_inflight / ponto_certo_llm_capacity`, % | Ocupação do único slot; não equivale ao uso de CPU |

Valores do [baseline público](../evidencias/cloud/observability-baseline.json), avaliados em **19/11/2026 às 12:26:14,725 UTC**, com janela de **12:21:14,725 a 12:26:14,725 UTC (5 min)** e histórico a cada 15 s:

| Sinal observado | Valor | Escopo do resultado |
|---|---:|---|
| Latência p95 | **24,6994 s** | Estimativa por buckets do histograma de perguntas na janela |
| Tráfego | **0,0666655 perguntas/s** | Taxa calculada na janela, não capacidade máxima |
| Erros HTTP 5xx | **0%** | Somente as perguntas e a janela consultadas |
| Saturação do slot LLM | **100%** | Um slot ocupado no instante final, não média de CPU/RAM |

A guarda histórica confirmou exclusivamente os dois alvos públicos esperados, evitando misturar séries locais. O [tráfego de observação](../evidencias/cloud/public-observation-traffic.json) registrou **12/12 perguntas bem-sucedidas**, documental/demo, entre 12:24:35 e 12:26:38 UTC. Essa série se sobrepõe ao recorte e termina depois dele; não é o denominador exato de todos os gráficos. `/metrics` sem Bearer retornou 401. O ensaio foi solicitado às **12:27:24 UTC** e executado de **12:27:30 a 12:29:31 UTC**, interrompendo a LLM por aproximadamente 120 s e iniciando o mesmo container. [Registro operacional](../evidencias/cloud/alert-exercise.json).

Coleta e avaliação a cada 15 s. As regras `PontoCertoPublicReadyUnavailable`, `PontoCertoModelNotReady` e `PontoCertoMetricsUnavailable` exigem condição por 1 min para reduzir ruído transitório; reservar cerca de 90 s para o ensaio. Prometheus registra `firing`; não foi configurado e-mail/WhatsApp. Retenção local: 10 dias ou 512 MB, o que vier primeiro.

Às **12:28:51,877 UTC**, `PontoCertoModelNotReady` e `PontoCertoPublicReadyUnavailable` estavam em [firing](../evidencias/cloud/observability-firing.json), com [captura legível](../evidencias/cloud/screenshots/alert-firing.jpg). Durante a falha, `/healthz` ficou em 200 e `/readyz` e a pergunta retornaram 503; a [interface informou indisponibilidade](../evidencias/cloud/screenshots/public-unavailable.jpg), sem simular resposta. A [recuperação](../evidencias/cloud/observability-recovered.json) confirmou prontidão 200, ausência de alertas ativos e três serviços saudáveis; o [smoke real](../evidencias/cloud/smoke-public-recovered.json) passou 5/5 até **12:30:41,038 UTC**. [Alertas resolvidos](../evidencias/cloud/screenshots/alert-recovered.jpg) e [interface recuperada](../evidencias/cloud/screenshots/public-recovered.jpg). O hash/tamanho dos pesos permaneceu igual. Houve stop/start da LLM, sem reboot do host ou reinício do proxy.

A janela móvel ainda contém as falhas anteriores: erro HTTP de **9,0136%** no disparo e **11,1216%** no snapshot após restauração, embora o serviço já estivesse pronto. Esses valores não foram substituídos por zero. O baseline anterior, a indisponibilidade e a recuperação têm horários próprios; o teste não estabelece SLA ou benchmark.

## Reprodução da implantação Azure da IA

1. Clone o repositório e confira o contrato IA. Na raiz, `docker compose -f compose.yaml config --quiet` e `docker compose -f compose.yaml up -d --build`. Defina um token de métricas por ambiente/arquivo protegido, sem incluí-lo no comando publicado. Execute `python3 scripts/smoke.py --base-url http://127.0.0.1:8000 --expect-mode demo --output reports/smoke-local.json`.
2. Ative Azure for Students em conta acadêmica autorizada. Confirme crédito, spending limit, região, SKU, quota e permissão. Leia [pré-requisitos e comandos de infraestrutura](../infra/OPERACAO.md). Não usar assinatura corporativa nem converter para modalidade paga.
3. Execute `bash infra/tf.sh init` e `bash infra/tf.sh validate`. Preencha `.tfvars` externo com assinatura, chave pública, DNS, `chilecentral` e imagem numérica. Verifique a URN exata com `az vm image show --location chilecentral --urn Canonical:ubuntu-24_04-lts:server:24.04.202611170`, incluindo x64/Gen2/Trusted Launch; listagem por prefixo pode selecionar daily/Gen1. Faça plano externo, revise recursos/custo/rede e só então aplique. Guarde evidência sanitizada, sem state completo.
4. Configure environment `production` limitado à `main`, IDs Azure e tokens em Secrets, RG/VM/URL em Variables. O pipeline aprova e publica os digests de app/LLM/proxy; pacotes privados exigem acesso de leitura do job e token efêmero no pull. Para reproduzir sem acesso aos pacotes, faça build dos Dockerfiles a partir do código público. O deploy via Managed Run Command precisa ser concluído de verdade; existência do workflow não o habilita automaticamente.
5. Verifique TLS, `/healthz`, `/readyz`, pergunta documental e chegada demo, fontes, modo, revisão e reinício. Guarde o smoke público. Para live, provisionar token SPTrans e validar retornos reais antes de afirmar cobertura.
6. Configure `python3 observability/configure.py --url https://URL-REAL` e suba `docker compose -f compose.monitoring.yaml up -d`. Gere perguntas reais, registre os quatro valores na janela, realize alerta controlado com recuperação, capture dashboard e pipeline sem segredos.
7. Preserve o manifesto e as evidências Azure como checkpoint da IA. A entrega Cloud deverá executar e documentar a mesma aplicação na AWS Sandbox, com seus próprios comandos, infraestrutura e provas; só depois será consolidado, gerado e revisado o PDF final Cloud. URL, provedor e revisão devem corresponder ao serviço medido. O envio acadêmico é feito por Pedro/equipe.

## Responsabilidades, dados e LGPD na Azure

| Camada | Responsável operacional |
|---|---|
| Datacenter, hardware e virtualização | Microsoft, conforme serviço IaaS contratado |
| Conta, IAM, rede, SO, patches, Docker, aplicação, modelo e segredos | Equipe, com Pedro responsável por IA/Cloud |
| Dashboard, coleta, interpretação, restauração e evidências | Equipe/operador do computador de monitoramento |
| Validação acadêmica e envio | Pedro ou integrante designado; não automatizado por este repositório |

O aplicativo não exige cadastro, CPF, telefone, nome ou geolocalização. Não mantém histórico de conversas nem analytics. Perguntas podem conter dados pessoais inseridos voluntariamente: a interface orienta não enviá-los. Processamento transitório ainda é tratamento; ausência de banco não significa ausência de dados. Uvicorn e Caddy têm access logs desabilitados; métricas usam rótulos controlados sem pergunta, IP ou linha escolhida. Logs técnicos têm rotação, mas precisam de inspeção para garantir que dependências não acrescentem conteúdo sensível.

A VM foi alocada em `chilecentral`, no Chile, fora do Brasil, conforme apply e leitura da API. A aplicação e a inferência autohospedada foram validadas publicamente nessa VM; metadados, serviços de controle e fornecedores podem ter outros fluxos. A seleção anterior de Brasil Sul foi descartada por restrições de SKU; não é residência efetiva. Antes de ampliar para uso real com dados pessoais, a equipe deve definir finalidade, base legal, aviso, canal de atendimento, retenção e mecanismo aplicável de transferência internacional, verificando contratos do provedor e orientação da ANPD. O desenho não é uma certificação de conformidade LGPD. Referências: [responsabilidade compartilhada Microsoft](https://learn.microsoft.com/azure/security/fundamentals/shared-responsibility) e [transferência internacional ANPD](https://www.gov.br/anpd/pt-br/assuntos/assuntos-internacionais/transferencia-internacional-de-dados).

## Crédito, capacidade e manutenção da Azure

Estimativa de [infra/OPERACAO.md](../infra/OPERACAO.md), preços Microsoft Retail API consultados em 19/11/2026, Linux `chilecentral`, 216 h (9 dias), com margem para manter o serviço até 27/11:

| Item | Referência | Consumo estimado de crédito |
|---|---:|---:|
| B2als_v2, 2 vCPU / 4 GiB | US$0,0526/h | US$11,3616 |
| Standard SSD E4 LRS, 32 GiB | US$3,36/mês | ~US$1,0080 |
| IPv4 Standard | US$0,005/h | US$1,0800 |
| Base | | **US$13,4496 (~US$13,45)** |

Disco proporcional usa mês de 30 dias. Operações SSD (US$0,0028/10 mil), saída de rede e duração maior podem alterar o total. Não é gasto realizado nem promessa de custo zero: a intenção é **R$0 desembolsado usando crédito educacional**. Students oferece US$100 por 12 meses, sem cartão, sujeito à verificação; crédito expirado/esgotado pode desabilitar o serviço. Não remover spending limit nem habilitar plano pago. O preflight confirmou SKU/quota e estimativa; somente o apply comprova alocação.

No CI, a política consultada em 19/11/2026 mantém gratuitos os runners padrão em repositórios públicos ([GitHub Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions)) e, atualmente, armazenamento e tráfego de imagens no GHCR ([GitHub Packages](https://docs.github.com/en/billing/concepts/product-billing/github-packages)). Artefatos do Actions têm franquia de armazenamento e uso acumulado por hora; a gratuidade dos runners não significa armazenamento ilimitado. O workflow retém relatórios por 14 dias e arquivos temporários de transferência de imagens por 2 dias. Já foram removidos quatro desses arquivos dos runs encerrados `44515603367` e `44517488349` (2.867.244.036 bytes), preservando relatórios e imagens GHCR: [registro da limpeza](../evidencias/cloud/temporary-artifact-cleanup.json). Reexecutar a publicação desses runs exige reconstruir os arquivos. A remoção reduz armazenamento futuro, sem apagar uso acumulado; este documento não afirma valor de fatura nem custo GitHub realizado.

Manter aplicação, repositório e evidências acessíveis **até pelo menos 27/11/2026 às 23h55, America/Sao_Paulo**, e confirmar fim da correção antes de encerrar. Não há desligamento automático. Conferir saldo, expiração, disco, prontidão e créditos de CPU; manter coleta local ativa e registrar eventuais lacunas. Uma VM única pode ter interrupções e não fornece SLA definido pela equipe.

Depois da liberação do responsável, preservar evidências e backup cifrado, revisar plano de destroy e remover somente o RG acadêmico/recursos geridos. Parar a VM não elimina custo de disco/IP. Revogar credenciais e federação no encerramento. Nunca limpar recursos corporativos.

## Rubrica e critérios de aceitação

Os nove checks do manifesto atual comprovam a fase **Azure**. Os critérios abaixo permanecem aplicáveis à nova entrega Cloud em **AWS Sandbox**, que ainda exige validação própria. A aceitação do laboratório foi relatada por Pedro; não transforma provas Azure em provas AWS.

| Rubrica Cloud | Peso | Configuração verificável | Evidência de execução necessária |
|---|---:|---|---|
| Containers | 2 | Dockerfiles, Compose, não root, pesos fixados | Build, usuários efetivos, healthchecks, inferência real e restart |
| Terraform | 3 | HCL, lockfile, NSG, state protegido | Apply real, recursos, rede e state protegido sem conteúdo sensível |
| CI/CD seguro | 4 | Gitleaks, Semgrep, Trivy, build, gates | Run aprovado e run barrado, commits, deploy ausente no bloqueio, atualização real |
| Observabilidade | 3 | Quatro métricas, dashboard e regras | Valores reais, alvo público, janela, alerta firing e recuperação |
| Documentação | 2 | Ficha, arquitetura, reprodução, responsabilidades | PDF legível, links e evidências correspondentes à versão publicada |

O material oficial traz 10 pontos/Teams na regra geral p.24 e 14 pontos/portal na rubrica Cloud p.52-53. Essa divergência é registrada, sem inventar equivalência ou decisão institucional. O prazo publicado é **19/11/2026 às 23h55 de São Paulo**. Pedro/equipe devem confirmar o canal exigido e realizar a submissão. Preparação técnica, repositório e PDF não são comprovante de envio.

## Manifesto e geração do PDF

**PDF final aguardando AWS.** O gerador e manifesto existentes refletem a fase Azure. Antes da geração final, adequar a narrativa, custos, links e seleção de evidências ao ambiente AWS efetivamente validado, preservando o histórico Azure para IA. Nenhum resultado AWS é declarado neste checkpoint.

O script [build-cloud-pdf.py](../scripts/build-cloud-pdf.py) lê a ficha do README e campos permitidos do manifesto. Não faz chamadas de rede, Git, cloud ou coleta de segredos. Aceita uma evidência apenas se o caminho local existir dentro do repositório ou houver link HTTP(S) sem credenciais/query. A presença de arquivo não verifica seu conteúdo: revisão humana/visual permanece necessária. Para apresentar um check como validado, exige `status: passed`, `scope`, `checked_at` e ao menos referência existente ou URL. Sem esses elementos, registra PENDENTE.

Esquema mínimo extensível (valores abaixo são marcadores de estrutura, não evidência):

```json
{
  "schema_version": 1,
  "updated_at": "DATA-ISO-DA-COLETA",
  "revision": "SHA-COMPLETO-DO-COMMIT",
  "repository_url": "https://github.com/Salvittis/ponto-certo",
  "public_url": "",
  "provisioning": {
    "status": "pending", "scope": "public", "checked_at": "",
    "region": "", "vm_size": "", "summary": "Conclusão do apply pendente",
    "evidence": []
  },
  "checks": {
    "docker": {
      "status": "pending", "scope": "local", "checked_at": "",
      "summary": "", "commit": "", "url": "", "evidence": []
    }
  },
  "metrics": {
    "scope": "", "target": "", "window": "",
    "latency_p95_seconds": null,
    "traffic_requests_per_second": null,
    "error_rate_percent": null,
    "saturation_percent": null
  },
  "screenshots": {
    "dashboard": {"path": "evidencias/cloud/dashboard.png", "scope": "", "caption": ""}
  }
}
```

Checks suportados: `docker`, `terraform`, `ci_pass`, `ci_block`, `public_app`, `restart`, `metrics`, `alert`, `recovery`. Estados: `passed`, `failed`, `partial`, `pending`, `in_progress`. Escopos: `local`, `public`, `configuration`. Screenshots opcionais: `pipeline_pass`, `pipeline_block`, `dashboard`, `alert`, `recovery`, `public_app`, `container`, `terraform`; cada um contém path, scope, caption e URL de origem opcional. Somente imagens existentes e declaradas no manifesto entram nos apêndices em paisagem, uma por página, com referência clicável na seção pertinente; ausência não reserva espaço vazio. Capturas locais de interface não são incluídas automaticamente; quando declaradas, devem ter escopo `local` e legenda **IA real local / dados demo**, sem serem promovidas a prova de nuvem. As evidências locais permanecem referenciadas pelo check `docker` de escopo local. O objeto opcional `costs` atualiza a estimativa com `region`, `checked_at`, `hours`, `vm_hourly_usd`, `ip_hourly_usd`, `disk_monthly_usd` e `total_estimate_usd`; valores ausentes continuam PENDENTE e não herdam preços de outra região.

```sh
python3 scripts/build-cloud-pdf.py --check
python3 scripts/build-cloud-pdf.py
```

Requer ReportLab e Pillow. No ambiente Codex, usar `/Users/salvitti/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`. Saída única: `output/pdf/Ponto-Certo-Deploy-Blindado.pdf`. Reexecutar substitui esse PDF usando as evidências atuais. O processo gera 12 seções principais, apêndices de capturas em paisagem e links clicáveis; revisar quantidade de páginas, renderização e legibilidade após cada geração. Antes de enviar, conferir que documento/manifesto/URL e commit correspondem à mesma entrega.

## Fontes oficiais e documentos de referência

- [Azure for Students](https://learn.microsoft.com/azure/education-hub/about-azure-for-students), [limite de gastos](https://learn.microsoft.com/azure/cost-management-billing/manage/spending-limit) e [crédito expirado/esgotado](https://learn.microsoft.com/azure/cost-management-billing/manage/azurestudents-subscription-disabled).
- [B2als_v2 e CPU credits](https://learn.microsoft.com/azure/virtual-machines/sizes/general-purpose/basv2-series), [Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices) e [IP público/DNS](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses).
- [Managed Run Command](https://learn.microsoft.com/azure/virtual-machines/linux/run-command-managed), [OIDC Azure/GitHub](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect) e [permissões Compute](https://learn.microsoft.com/azure/role-based-access-control/permissions/compute).
- [Provider AzureRM 5.14.0](https://registry.terraform.io/providers/hashicorp/azurerm/5.14.0), [state sensível](https://developer.hashicorp.com/terraform/language/manage-sensitive-data) e [backend local](https://developer.hashicorp.com/terraform/language/backend/local).
- [Docker no Ubuntu](https://docs.docker.com/engine/install/ubuntu/), [Prometheus alert rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) e [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).
- [Modelo Qwen e licença](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF), [llama.cpp b12464](https://github.com/ggml-org/llama.cpp/releases/tag/b12464), [SPTrans desenvolvedores](https://www.sptrans.com.br/desenvolvedores) e [documentação Olho Vivo](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api).
- PDF oficial da disciplina: `Desafio-FIAP-GS-CitizenTech 4ES.pdf`, p.18-25 (orientações/Ficha), p.28-31 (IA), p.51-53 (Cloud), preservado na pasta FIAP.
