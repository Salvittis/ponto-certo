# Cloud no AWS Academy — Ponto Certo

A entrega de Cloud usa o **AWS Academy Sandbox**, conforme a orientação do professor relatada por Pedro em 19/11/2026. A aplicação de IA permanece separadamente na [Azure](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com), com permanência planejada até **27/11/2026 às 23h55 de São Paulo**. São duas implantações da mesma aplicação, modelo, base e contrato funcional. Evidências de uma plataforma não comprovam a outra.

O Sandbox desta sessão informou duração de **180 minutos**, com início em **19/11/2026 às 09:35:56 de São Paulo** (`12:35:56Z`) e limite declarado de **12:35:56 de São Paulo** (`15:35:56Z`). O guia observado informa que recursos e dados são apagados no encerramento ou vencimento da sessão. Esse prazo é uma janela operacional, não um saldo financeiro nem garantia de renovação. A aceitação desse ambiente para Cloud foi relatada por Pedro; não foi deduzida do PDF da disciplina.

## Estado deste checkpoint

A [aplicação pública AWS](https://54-210-161-95.sslip.io) foi comprovada em modo demo na revisão `60aeeddc0509cf6c82c65485f67fae67ad494a62`. O [ensaio controlado da LLM](../evidencias/aws/alert-exercise.json), comando SSM `d1be6c52-e9ca-4a4b-9e9b-0213f572438c`, foi concluído com **12/12 checks aprovados**, incluindo alertas, recuperação, inferência e integridade das imagens/pesos. A conclusão foi registrada em **19/11/2026 às 13:25:15 UTC** (10:25:15 de São Paulo). O PDF final ainda precisa de consolidação, geração e revisão visual.

| Etapa | Resultado observado |
|---|---|
| Conta e escopo | STS conferiu a conta Academy esperada; perfil e arquivos de credenciais separados das contas pessoal e de trabalho. Região `us-east-1`. |
| Terraform inicial | **11 recursos adicionados, 0 alterados e 0 destruídos**. Plano e aplicação reais preservados. |
| Primeiro bootstrap | Falhou por indisponibilidade do pacote APT `awscli`. O diagnóstico SSM executou, mas não comprovou prontidão do host. |
| Correção do bootstrap | Terraform substituiu uma EC2, preservando a rede: **1 adição, 0 alterações e 1 destruição**. AWS CLI 2.41.1 oficial verificada por GPG; depois, `cloud-init done` sem erros, Docker 29.10.0 e Compose 5.8.0. |
| Infraestrutura final | Instância `i-0cd7e82843509189b`; 17 checks aprovados e plano Terraform posterior sem mudanças. |
| Pipeline/deploy | [Run 44528188191](https://github.com/Salvittis/ponto-certo/actions/runs/44528188191) aprovado às **13:07:28 UTC**: nove jobs, **78/78 testes**, scanners sem bloqueadores na política registrada e deploy AWS/Azure dos mesmos digests. |
| HTTPS/inferência | TLS 1.3, hostname/cadeia validados, HTTP→HTTPS 308, smoke **5/5** e 12 inferências complementares aprovadas. |
| Containers | Proxy, API e LLM saudáveis, UID efetivo 10001, readonly, capabilities removidas, `no-new-privileges`; pesos com SHA/tamanho fixados. |
| Observabilidade | Baseline público coletado às **13:20:48 UTC**, com quatro valores disponíveis e alvos AWS qualificados. Ensaio controlado concluído: dois alertas firing e posterior recuperação sem alertas ativos. |

Infraestrutura: [apply inicial](../evidencias/aws/terraform-applied.json), [plano inicial](../evidencias/aws/terraform-plan.txt), [primeira falha](../evidencias/aws/bootstrap-failed-first.json), [substituição](../evidencias/aws/terraform-replacement.json), [bootstrap corrigido](../evidencias/aws/bootstrap-check-2.json) e [verificação posterior](../evidencias/aws/infrastructure-verified.json). O `Status=Success` da **primeira consulta de diagnóstico** não tornou aquela inicialização válida; o erro original permanece preservado.

Publicação: [pipeline](../evidencias/aws/pipeline-passed.json), [scanners/testes/deploy/smoke](../evidencias/aws/security-passed-summary.json), [prontidão/revisão](../evidencias/aws/public-first-ready.json), [rede/TLS](../evidencias/aws/public-network.json), [runtime](../evidencias/aws/containers-baseline.json) e [captura da interface](../evidencias/aws/screenshots/public-app.jpg). O smoke de **13:06:07–28 UTC** verificou saúde, prontidão, modo e duas consultas reais à LLM; a previsão de ônibus era sintética. O SecureString temporário do deploy foi excluído, conforme `parameter_cleanup=deleted`.

O [tráfego complementar](../evidencias/aws/public-observation-traffic.json) passou 12/12 inferências entre **13:16:12 e 13:17:50 UTC**, com 7,180–8,996 segundos por chamada. Não é benchmark de capacidade. Os [contratos de falha/ausência](../evidencias/aws/public-failure-contracts.json) também passaram, sem registrar texto livre de perguntas ou respostas.

O [baseline Prometheus](../evidencias/aws/observability-baseline.json) registra janela de cinco minutos terminando em **13:20:48,444 UTC**: p95 aproximado por buckets **9,6895 s**, tráfego **0,0491223 perguntas/s**, HTTP 5xx **0%** e saturação instantânea do slot LLM **0%**. Ambos os alvos estavam UP no instante final e não havia alertas ativos; o histórico móvel ainda contém amostras do incidente anterior de coleta. Saturação 0% significa slot livre no instante amostrado, não ausência de inferências no período.

O [incidente de conectividade do observador Mac](../evidencias/aws/connectivity-incident.json), aproximadamente **13:08–13:15 UTC**, gerou timeouts e alertas locais enquanto a EC2 e uma VM Azure independente alcançavam a prontidão pública. A causa não foi determinada; não há evidência de queda geral da aplicação. Um problema posterior e distinto no bind mount do token foi corrigido recriando somente Prometheus AWS, preservando o volume. Esses eventos não são o ensaio planejado da LLM. Nesse ensaio, as primeiras [verificações de indisponibilidade](../evidencias/aws/public-controlled-unavailable.json), às 13:22:00–05 UTC, registraram `/healthz` 200, `/readyz` 503 e pergunta `unavailable`/503; o disparo e a restauração foram depois confirmados pelo ensaio completo abaixo.

A Azure também passou o deploy da revisão `60aeedd` nesse run e permanece pública em **demo**. Um [preflight restrito SPTrans/LLM](../evidencias/cloud/azure-live-preflight.json) passou às 13:08:44–58 UTC com uma previsão real e timestamps frescos; seu escopo é execução direta do motor, não HTTP público. A publicação live aguarda hardening de frescor/coerência do código da parada, novo preflight e smoke HTTP na revisão corrigida. Não se declara cobertura integral da SPTrans nem se altera o experimento congelado.

## Ensaio controlado e recuperação comprovados

O comando conferiu a revisão antes da falha e usou lock exclusivo, trap de restauração e timer independente de contingência. Somente o container LLM foi parado; não houve reboot do host, parada da API, alteração de rede ou substituição de imagem.

| Etapa em 19/11/2026 | São Paulo | Evidência |
|---|---|---|
| Parada da LLM | 10:21:35 (`13:21:35Z`) | [Comando e 12 checks](../evidencias/aws/alert-exercise.json) |
| Contrato público durante a falha | 10:22:00–05 | [API viva/200, prontidão e pergunta/503](../evidencias/aws/public-controlled-unavailable.json) |
| Dois alertas firing | 10:22:57 | [ModelNotReady e PublicReadyUnavailable](../evidencias/aws/observability-firing.json) |
| Solicitação de reinício da LLM | 10:23:36 (`13:23:36Z`) | [Registro do ensaio](../evidencias/aws/alert-exercise.json) |
| Smoke depois do retorno | 10:23:44–10:24:13 | [5/5 checks, incluindo inferência documental/demo](../evidencias/aws/smoke-public-recovered.json) |
| Recuperação sem alertas ativos | 10:24:28 | [Prontidão 200, modelo pronto, alertas vazios](../evidencias/aws/observability-recovered.json) |

O snapshot intermediário às **10:23:53** já via prontidão 200, mas ainda mostrava firing na avaliação Prometheus; por isso a conclusão usa a observação posterior de **10:24:28**. Os [containers após reinício](../evidencias/aws/containers-recovered.json) ficaram running/healthy com UID 10001, os mesmos três digests e o mesmo GGUF de 1.117.320.736 bytes/SHA-256 fixado. O smoke observou inferência documental em 13,265 s e chegada demo em 14,229 s; amostras individuais, sem afirmação de benchmark.

Capturas reais: [dashboard anterior](../evidencias/aws/screenshots/dashboard-baseline.jpg), [alertas firing](../evidencias/aws/screenshots/alerts-firing.jpg), [dashboard durante a falha](../evidencias/aws/screenshots/dashboard-firing.jpg), [alertas resolvidos](../evidencias/aws/screenshots/alerts-recovered.jpg) e [dashboard recuperado](../evidencias/aws/screenshots/dashboard-recovered.jpg). O [registro de capturas](../evidencias/aws/browser-observations.json) conserva horário, origem, SHA e identificação do ensaio; não mistura o incidente do observador com a falha provocada da LLM.

Os snapshots de disparo e recuperação preservam **0% de HTTP 5xx**, embora o contrato público tenha registrado 503. Na revisão `60aeedd`, a série do primeiro 503 surgiu em 1, sem amostra prévia em zero; a consulta histórica confirmou a limitação de `rate(...[5m])`. Isso não invalida os alertas nem a restauração comprovada. A inicialização das séries conhecidas em zero e o registro dos limites anteriores ao roteamento foram corrigidos no código local, com testes de primeira resposta 503 e rejeição 413 aprovados; a nova imagem ainda precisa ser publicada e validada no Prometheus. [Detalhamento e referência oficial](OBSERVABILIDADE.md#limitação-histórica-da-primeira-falha-e-correção-preparada). Nenhuma taxa histórica foi reescrita.

## Arquitetura e separação

O código em [infra/aws](../infra/aws/main.tf) cria uma VPC, subnet pública, Internet Gateway, tabela/rota/associação, Security Group, três regras de rede e uma EC2. A máquina usa `t2.medium` em modo de créditos **Standard**, Ubuntu Server 24.04 AMD64 da Canonical e volume raiz **gp2 de 32 GiB cifrado**, removido com a instância. A AMI é explicitamente fixada e conferida por proprietário `099720109477`, nome, arquitetura e virtualização; o plano inicial usou `ami-0109d2b556bd3d7e1` em `us-east-1a`.

Somente TCP **80 e 443** têm entrada pública. Não há chave SSH provisionada nem porta 22 aberta. Administração e inspeção usam SSM por conexão de saída. IMDSv2 é obrigatório, com limite de um salto, para que os containers da aplicação não dependam das credenciais do host. A saída do Security Group é ampla para SSM, atualizações, imagens, ACME e fontes da aplicação; não se reivindica uma política restritiva de egress.

O laboratório fornece `LabRole` e `LabInstanceProfile`; o projeto apenas lê e associa esse perfil existente. Não cria IAM, chave de acesso permanente, OIDC, keypair ou permissões novas. Os recursos de apoio criados pelo próprio Academy, como Bastion Host e Lab Instance, não são administrados por este Terraform.

O [Compose de produção](../compose.production.yaml) contém proxy Caddy, API FastAPI e LLM Qwen. As três imagens são publicadas e implantadas por digest depois dos gates. A [inspeção AWS](../evidencias/aws/containers-baseline.json) confirmou UID 10001, filesystem somente leitura, remoção de capabilities e `no-new-privileges` nos três containers. Em outra sessão/release, repetir a conferência. Somente o proxy publica portas. API, LLM e administração não recebem portas públicas.

O hostname temporário é derivado do IPv4 no domínio `sslip.io`. Em uma nova aplicação, o output `public_url` é apenas um alvo até DNS, certificado, revisão e inferência passarem. Nesta sessão, esses checks já passaram para `https://54-210-161-95.sslip.io`. IP e hostname podem mudar com substituição ou outra sessão. O DNS gratuito é uma dependência externa, sem domínio próprio ou SLA contratado. Os certificados são solicitados pelo Caddy via ACME; ter uma URL no Terraform não comprova sua emissão.

## Reproduzir com credenciais da sessão

Os comandos abaixo partem da raiz do repositório. Terraform, AWS CLI, GitHub CLI, Python e Docker precisam estar disponíveis. Antes de começar, conferir a sessão ativa e tempo suficiente para provisionar, publicar, testar e preservar as provas. Nunca usar credenciais da TBC, o perfil AWS padrão ou a conta Azure como substitutos.

1. Guardar as três credenciais temporárias fornecidas pelo Lab em arquivo próprio fora do Git, com modo **0600** e diretório **0700**. Não colar os valores no terminal como argumento, no README, em `tfvars`, em `user_data`, em capturas ou em mensagens.
2. Selecionar explicitamente o arquivo/perfil Academy e limpar outras fontes de credenciais antes de chamar AWS CLI ou Terraform. O exemplo apenas seleciona caminhos; não imprime valores:

   ```sh
   unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
   unset AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_ROLE_SESSION_NAME AWS_DEFAULT_PROFILE
   export AWS_SHARED_CREDENTIALS_FILE="$HOME/.local/share/ponto-certo/aws-lab/credentials"
   export AWS_CONFIG_FILE="$HOME/.local/share/ponto-certo/aws-lab/config"
   export AWS_PROFILE=ponto-certo-academy
   export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
   export AWS_EC2_METADATA_DISABLED=true AWS_PAGER=''
   aws sts get-caller-identity
   ```

3. Confirmar que o `Account` retornado é exatamente o da sessão, e conferir `LabInstanceProfile`, disponibilidade da zona/tamanho e a AMI Canonical. O `allowed_account_ids` do provider precisa conter somente essa conta Academy.
4. Criar um arquivo privado `academy.tfvars.json` fora do checkout com `allowed_account_ids`, `ubuntu_ami_id` e `availability_zone`. Esses valores são entradas verificadas, não segredos; mesmo assim o arquivo permanece fora do Git, conforme a entrega.
5. Usar o [wrapper AWS](../infra/aws/tf.sh), que separa state, cache e metadados do namespace Azure:

   ```sh
   umask 077
   export PC_AWS_TERRAFORM_STATE_DIR="$HOME/.local/share/ponto-certo/terraform-aws"
   bash infra/aws/tf.sh init
   bash infra/aws/tf.sh validate
   bash infra/aws/tf.sh plan \
     -var-file="$PC_AWS_TERRAFORM_STATE_DIR/academy.tfvars.json" \
     -out="$PC_AWS_TERRAFORM_STATE_DIR/academy.tfplan"
   # Inspecionar o plano salvo antes de executar as alterações.
   bash infra/aws/tf.sh apply "$PC_AWS_TERRAFORM_STATE_DIR/academy.tfplan"
   bash infra/aws/tf.sh output
   ```

O wrapper aceita `PC_AWS_TERRAFORM_BIN` para selecionar um binário específico. Ele recusa state dentro do checkout ou em diretórios sobrepostos ao state Azure. Os arquivos privados e backups ficam em 0600, com diretórios 0700. O backup observado fica no mesmo disco local cifrado; não é cópia externa nem backend remoto com coordenação de equipe. Somente um operador deve aplicar esse state.

Depois do apply, confirmar checks EC2 e SSM `Online`, `cloud-init` concluído sem erro, `/opt/ponto-certo/bootstrap-ready.txt`, Docker, Compose e AWS CLI funcionais. A inspeção deve selecionar campos permitidos; não imprimir ambiente de processos, `runtime.env`, tokens, comandos com segredos ou logs arbitrários da aplicação.

## Pipeline e publicação

O [guia de segurança AWS](../security/AWS-DEPLOY.md) descreve as Secrets e Variables do environment `aws-academy`, restrito à branch `main`. As três credenciais temporárias do Lab e `AWS_METRICS_TOKEN` são exclusivos desse ambiente. As Variables identificam conta, região, instância, URL e término declarado da sessão; o modo permanece demo até validação explícita de live.

Somente habilitar a Variable **do repositório** `AWS_ENABLED=true` depois de conferir o host e atualizar instância/URL. Um push em `main` executa Gitleaks no histórico, Semgrep, testes e build/Trivy das três imagens; a publicação depende de todos os gates. Os arquivos de imagem examinados são publicados sem rebuild, e os jobs Azure e AWS consomem os mesmos digests. O job AWS é independente do Azure: sua flag não desliga nem altera a hospedagem da IA. `workflow_dispatch` não publica nem implanta neste fluxo.

O deploy AWS valida conta, instância, tag `project=ponto-certo`, estado e SSM antes de escrever. O runner cria um SecureString Standard temporário, fora do Terraform, contendo os segredos necessários. Run Command recebe apenas código/configuração públicos e nome/versão desse parâmetro. O host recupera o valor com o perfil do Lab; o token GHCR de curta duração é usado por stdin e removido do diretório temporário de login após o pull. O token de métricas necessário à aplicação fica no `runtime.env` 0600.

O runner exige `SSM Status=Success` e `ResponseCode=0`, confere HTTPS, revisão, prontidão e perguntas com inferência real. Falha na validação pública aciona rollback com guarda de revisão. O SecureString é excluído no `finally`; falha de limpeza reprova o job. Cancelamento, expiração ou indisponibilidade podem impedir a limpeza, exigindo conferência posterior. Não há TTL automático para esse parâmetro Standard.

## Evidências da entrega AWS

A entrega deve preservar fatos associados ao destino, horário e SHA, incluindo:

- Plano/apply e identificação da EC2, volume, perfil e regras de rede efetivamente aplicados.
- Pipeline barrado e corrigido, relatórios dos scanners, imagens aprovadas e execução do deploy AWS. O run barrado do mesmo repositório demonstra o gate; somente um deploy AWS aprovado comprova sua publicação nessa plataforma.
- HTTPS e interface pública, `/healthz`, `/readyz`, revisão correta e perguntas documental/demonstrativa com inferência real.
- Inspeção sanitizada de Compose/containers, UID, endurecimento, digests e hash/tamanho dos pesos; não apenas o conteúdo esperado nos arquivos.
- Quatro sinais de observabilidade, alerta realmente disparado no alvo AWS, restauração, prontidão e smoke depois da recuperação.

Usar o [monitoramento AWS separado](OBSERVABILIDADE-AWS.md): Prometheus local em `127.0.0.1:9091` e Grafana em `127.0.0.1:3002`, com projeto, alvos, token e volumes próprios. O coletor deve apontar a URL AWS final e salvar em `evidencias/aws/`; suas guardas impedem atribuir séries Azure ou de outro IP a esse destino. As interfaces administrativas permanecem locais. Após uma queda de energia, reiniciar/conferir esse monitor não equivale a reiniciar a aplicação na nuvem.

O PDF final de Cloud deve reunir as provas reais legíveis e seus links. Capturas Azure anteriores e o exemplo enviado por Pedro não podem preencher lacunas da AWS. Neste checkpoint, infraestrutura, publicação, inferência e runtime AWS estão comprovados; quatro métricas, alerta provocado e recuperação também passaram. A consolidação final, geração e revisão visual do PDF ainda estão pendentes. A submissão institucional continua com Pedro/equipe.

## Renovação, encerramento e custos

Antes do fim da janela, preservar JSON, logs sanitizados, screenshots e o PDF fora do Sandbox. Desativar `AWS_ENABLED` ao encerrar os trabalhos dessa sessão, conferir a exclusão de parâmetros temporários e parar somente o projeto de monitoramento AWS quando o alvo deixar de existir. A aplicação Azure permanece em seu ciclo independente.

Para outra sessão, obter novas credenciais pelo Academy e conferir novamente a conta. Não reutilizar tokens expirados nem declarar renovação automática. Se a conta mudou, usar outro diretório de state AWS e `allowed_account_ids` correspondente, preservando o histórico anterior; nunca apontar um state para uma conta diferente. Na mesma conta, fazer backup do state e um novo plano com refresh normal para reconhecer recursos removidos pelo Sandbox. Não reutilizar o plano antigo nem apagar state para esconder diferenças. Revisar e aplicar o novo plano, conferir bootstrap e atualizar Secrets/Variables, ID, IP, URL e prazo; executar novamente o pipeline completo e as provas necessárias.

Não usar `End Lab` antes de preservar as evidências: o encerramento apaga os recursos e dados segundo o guia observado. Uma sessão nova não garante o mesmo endereço nem restaura os containers anteriores. Reconstituição vem do Terraform, imagens aprovadas e configuração protegida.

O escopo autorizado usa a conta acadêmica gerenciada, sem cadastrar conta AWS pessoal ou meio de pagamento. Uma estimativa de preços públicos para EC2, volume e IPv4 serve à análise de arquitetura; não representa cobrança pessoal nem o saldo do Lab. A duração de três horas não é crédito monetário. A [estimativa ilustrativa registrada](../evidencias/aws/cost-estimate.json) é **US$0,16753** para três horas de uma t2.medium, gp2 de 32 GiB e um IPv4 em `us-east-1`, usando mês de 720 horas para o disco. Ela exclui tráfego, recursos de apoio do Academy, primeira EC2 defeituosa, tempo extra e CI; não é consumo medido ou cobrança pessoal. A Azure utiliza separadamente os créditos Students e o limite de gastos ativo; não converter a assinatura para paga nem remover esse limite.
