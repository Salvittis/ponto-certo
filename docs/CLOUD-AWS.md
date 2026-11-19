# Cloud no AWS Academy — Ponto Certo

A entrega de Cloud usa o **AWS Academy Sandbox**, conforme a orientação do professor relatada por Pedro em 19/11/2026. A aplicação de IA permanece separadamente na [Azure](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com), com permanência planejada até **27/11/2026 às 23h55 de São Paulo**. São duas implantações da mesma aplicação, modelo, base e contrato funcional. Evidências de uma plataforma não comprovam a outra.

O Sandbox desta sessão informou duração de **180 minutos**, com início em **19/11/2026 às 09:35:56 de São Paulo** (`12:35:56Z`) e limite declarado de **12:35:56 de São Paulo** (`15:35:56Z`). O guia observado informa que recursos e dados são apagados no encerramento ou vencimento da sessão. Esse prazo é uma janela operacional, não um saldo financeiro nem garantia de renovação. A aceitação desse ambiente para Cloud foi relatada por Pedro; não foi deduzida do PDF da disciplina.

## Estado deste checkpoint

| Etapa | Resultado observado |
|---|---|
| Conta e escopo | STS conferiu a conta Academy esperada; perfil e arquivos de credenciais separados das contas pessoal e de trabalho. Região `us-east-1`. |
| Terraform inicial | **11 recursos adicionados, 0 alterados e 0 destruídos**. Plano e aplicação reais preservados. |
| Primeiro bootstrap | SSM ficou `Online`, mas o bootstrap falhou porque o pacote APT `awscli` não estava disponível na imagem Ubuntu utilizada. A criação da EC2 não comprovou a aplicação. |
| Correção do bootstrap | Em preparação neste checkpoint. A EC2 será substituída pelo Terraform; ID, IP e URL anteriores não devem ser usados como endereço final. |
| Código do deploy AWS | Implementado e validado localmente: **78 testes aprovados**, incluindo 24 novos testes AWS e os 54 anteriores; actionlint, Bash e Semgrep aprovados. Isso ainda não comprova execução remota. |
| Pipeline/deploy AWS | Ainda não verificados neste checkpoint; `AWS_ENABLED=false` durante a preparação do host. |
| HTTPS, inferência, métricas e recuperação AWS | Ainda aguardam execução no destino AWS definitivo. |

As fontes desse checkpoint são o [registro de infraestrutura](../evidencias/aws/terraform-applied.json), o [plano inicial](../evidencias/aws/terraform-plan.txt), o [log do primeiro apply](../evidencias/aws/terraform-apply.txt) e a [falha real do primeiro bootstrap](../evidencias/aws/bootstrap-failed-first.json). O `Status=Success` da consulta SSM significa somente que o comando de diagnóstico executou; seu conteúdo registra `cloud-init status=error` e `BOOTSTRAP_PENDING`.

Na Azure, o [run 44525695720](https://github.com/Salvittis/ponto-certo/actions/runs/44525695720) concluiu com sucesso na revisão `540cffe0f31bacde6f0564adc0ff2adf390e6052`; a prontidão pública foi conferida nessa revisão após a interrupção de energia. As evidências detalhadas anteriores continuam em [STATUS-CLOUD.md](STATUS-CLOUD.md). O modo de transporte permanece **demo**, com dados sintéticos identificados e inferência real da LLM; SPTrans live não está verificada.

## Arquitetura e separação

O código em [infra/aws](../infra/aws/main.tf) cria uma VPC, subnet pública, Internet Gateway, tabela/rota/associação, Security Group, três regras de rede e uma EC2. A máquina usa `t2.medium` em modo de créditos **Standard**, Ubuntu Server 24.04 AMD64 da Canonical e volume raiz **gp2 de 32 GiB cifrado**, removido com a instância. A AMI é explicitamente fixada e conferida por proprietário `099720109477`, nome, arquitetura e virtualização; o plano inicial usou `ami-0109d2b556bd3d7e1` em `us-east-1a`.

Somente TCP **80 e 443** têm entrada pública. Não há chave SSH provisionada nem porta 22 aberta. Administração e inspeção usam SSM por conexão de saída. IMDSv2 é obrigatório, com limite de um salto, para que os containers da aplicação não dependam das credenciais do host. A saída do Security Group é ampla para SSM, atualizações, imagens, ACME e fontes da aplicação; não se reivindica uma política restritiva de egress.

O laboratório fornece `LabRole` e `LabInstanceProfile`; o projeto apenas lê e associa esse perfil existente. Não cria IAM, chave de acesso permanente, OIDC, keypair ou permissões novas. Os recursos de apoio criados pelo próprio Academy, como Bastion Host e Lab Instance, não são administrados por este Terraform.

O [Compose de produção](../compose.production.yaml) contém proxy Caddy, API FastAPI e LLM Qwen. As três imagens são publicadas e implantadas por digest depois dos gates. O desenho exige UID 10001, filesystem somente leitura, remoção de capabilities e `no-new-privileges`; essas propriedades precisam ser confirmadas novamente nos containers AWS. Somente o proxy publica portas. API, LLM e administração não recebem portas públicas.

O hostname temporário é derivado do IPv4 no domínio `sslip.io`. O output `public_url` é um **alvo de implantação** até DNS, certificado HTTPS, revisão e inferência externa passarem. IP e hostname podem mudar com substituição ou outra sessão. O DNS gratuito é uma dependência externa, sem domínio próprio ou SLA contratado. Os certificados são solicitados pelo Caddy via ACME; ter uma URL no Terraform não comprova sua emissão.

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

O PDF final de Cloud deve reunir as provas reais legíveis e seus links. Capturas Azure anteriores e o exemplo enviado por Pedro não podem preencher lacunas da AWS. Até o checkpoint acima, essas validações AWS ainda estão pendentes. A submissão institucional continua com Pedro/equipe.

## Renovação, encerramento e custos

Antes do fim da janela, preservar JSON, logs sanitizados, screenshots e o PDF fora do Sandbox. Desativar `AWS_ENABLED` ao encerrar os trabalhos dessa sessão, conferir a exclusão de parâmetros temporários e parar somente o projeto de monitoramento AWS quando o alvo deixar de existir. A aplicação Azure permanece em seu ciclo independente.

Para outra sessão, obter novas credenciais pelo Academy e conferir novamente a conta. Não reutilizar tokens expirados nem declarar renovação automática. Se a conta mudou, usar outro diretório de state AWS e `allowed_account_ids` correspondente, preservando o histórico anterior; nunca apontar um state para uma conta diferente. Na mesma conta, fazer backup do state e um novo plano com refresh normal para reconhecer recursos removidos pelo Sandbox. Não reutilizar o plano antigo nem apagar state para esconder diferenças. Revisar e aplicar o novo plano, conferir bootstrap e atualizar Secrets/Variables, ID, IP, URL e prazo; executar novamente o pipeline completo e as provas necessárias.

Não usar `End Lab` antes de preservar as evidências: o encerramento apaga os recursos e dados segundo o guia observado. Uma sessão nova não garante o mesmo endereço nem restaura os containers anteriores. Reconstituição vem do Terraform, imagens aprovadas e configuração protegida.

O escopo autorizado usa a conta acadêmica gerenciada, sem cadastrar conta AWS pessoal ou meio de pagamento. Uma estimativa de preços públicos para EC2, volume e IPv4 serve à análise de arquitetura; não representa cobrança pessoal nem o saldo do Lab. A duração de três horas não é crédito monetário. O cálculo final deve identificar fontes, região, duração e exclusões — tráfego, recursos de apoio do próprio Academy e diferenças de tempo de execução — sem assumir custo zero universal. A Azure utiliza separadamente os créditos Students e o limite de gastos ativo; não converter a assinatura para paga nem remover esse limite.
