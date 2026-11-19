# Infraestrutura Azure Students - Ponto Certo

**Provisionamento: PENDENTE.** Este módulo é preparação reproduzível para uma
assinatura acadêmica Azure for Students. Validação estática não comprova conta
ativa, saldo, capacidade, provisionamento ou publicação. O estado e as evidências
da operação ficam em [`docs/STATUS-CLOUD.md`](../docs/STATUS-CLOUD.md).

Verificações locais de 19/11/2026: Terraform 1.17.2 com provider 5.14.0 passou em
`validate`; YAML cloud-init e sintaxe Bash do bootstrap passaram. FileVault do
Mac do operador retornou `On`, e a pasta de state/data está em modo 700. Ainda
não há state de recursos provisionados nem backup de um apply; esses fatos não
atestam infraestrutura em nuvem.

Não usar credenciais, conta ou faturamento da TBC. O `subscription_id` é obrigatório
e deve identificar a assinatura acadêmica autorizada por Pedro. Nenhuma assinatura
é criada, convertida para paga ou tem seu spending limit removido pelo Terraform.

## Desenho proposto

| Recurso | Configuração |
|---|---|
| Resource group | Exclusivo para FIAP, prefixo `ponto-certo-fiap` |
| VM | Ubuntu Server 24.04 x64, versão da imagem fixada, `Standard_B2als_v2` |
| Capacidade | 2 vCPUs, 4 GiB RAM; CPU burst, base 30% e banco de créditos |
| Disco | OS Standard SSD LRS, 32 GiB, cifrado em repouso pela plataforma |
| Rede | VNet/subnet/NIC dedicadas; IP público Standard estático |
| DNS/TLS | `<label>.<região>.cloudapp.azure.com`; Caddy emite/renova TLS |
| Entrada | Somente TCP 80 (ACME/redirect) e 443 (MVP HTTPS) |
| Administração | Azure Managed Run Command; nenhuma regra SSH/RDP |
| Aplicação | Compose com app, llama.cpp e Caddy, definido no repositório |
| Observabilidade | Prometheus/Grafana locais monitoram a URL pública autenticada |

Região candidata `eastus2` (EUA), sujeita a políticas, quota e disponibilidade da
assinatura acadêmica. O PDF de Cloud registra a localização realmente aplicada.
Não há GPU, banco, balanceador pago, NAT Gateway, Azure Bastion ou ACR. Imagens
aprovadas são públicas no GHCR. O Qwen 1,5B quantizado roda nesta VM e não chama
uma LLM comercial externa.

Aplicação e modelo não publicam suas portas diretamente no host. Caddy é a única
entrada; a LLM usa o DNS da rede Compose. A NSG permite só 80/443 e nega todas as
demais entradas, inclusive a regra padrão de entrada da VNet. A chave pública SSH
é exigida pelo recurso Azure para a conta local; isso não abre 22. Senhas de login
estão desabilitadas. Saída permite download de imagens/atualizações, Azure Agent,
ACME e fontes públicas; não há política de restrição de egress neste MVP.

Pesos e base documental vêm das imagens versionadas. O disco mantém imagens e
volumes de certificados do Caddy após reinício. Após recriação, baixar as mesmas
imagens aprovadas. Não tratar diretório de container como backup. Consultas e
posições pessoais não devem ser persistidas em logs ou volume de aplicação.

## Bootstrap, containers e publicação

`cloud-init.yaml` instala Docker e o plugin Compose pelo repositório APT oficial,
habilita rotação local de logs e prepara `/opt/ponto-certo` como root. Não contém
segredo, aplicação, token SPTrans, token de métricas ou chave privada. As versões
instaladas ficam em `docker-version.txt` e `compose-version.txt` nesse diretório.
As imagens da aplicação/modelo usam usuário não root. O daemon Docker e o agente
administrativo do host são privilegiados; isso deve ser distinguido do usuário
dos processos dentro dos containers. Nenhum usuário é adicionado ao grupo Docker
e o socket Docker não é exposto na rede ou montado na aplicação.

O pipeline aplica o Compose somente após build, Gitleaks, Semgrep e Trivy passarem.
Deve aguardar `cloud-init status --wait`, enviar os arquivos da versão aprovada e
rodar o deploy por Managed Run Command. Terraform administra host/rede/identidade;
CI administra a versão dos containers, sem editar a infraestrutura a cada release.
O término do bootstrap não prova que o MVP está publicado.

## Identidade GitHub e menor privilégio

O módulo cria uma identidade gerenciada **não anexada à VM**. Assim, o container
não pode obtê-la via metadata do host. A credencial federada confia somente em
`repo:<owner/repo>:environment:production`, emitida por
`https://token.actions.githubusercontent.com` para `api://AzureADTokenExchange`.

Antes de habilitar o deploy, o GitHub environment `production` deve permitir apenas
a branch `main`; o workflow também precisa restringir o job de publicação a `main`.
Quando OIDC usa environment, o subject não contém a branch: a restrição de branch
do environment é parte necessária do controle, não pode ser presumida pelo HCL.

A função RBAC própria concede leitura da VM/instanceView e operações read/write/
delete dos Managed Run Commands, com atribuição somente nesta VM. Não concede
criação de VMs, alteração de rede, IAM ou acesso a outros recursos. Executar
comandos no host continua sendo poder administrativo; proteger `main`, workflow
e environment. A identidade inicial que aplica Terraform precisa de permissão
para criar recursos, role definitions e role assignments no resource group.
Se o tenant FIAP restringir essa capacidade, registrar o bloqueio; não abrir
permissões de outra organização como atalho.

Configurar os outputs `github_client_id`, `tenant_id` e `subscription_id` como
`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` em GitHub Secrets.
Não é necessário secret duradouro da identidade: `azure/login` usa OIDC com
`id-token: write`. Os IDs não são senhas, mas continuam no canal de configuração.

`SPTRANS_TOKEN` e `METRICS_TOKEN` são enviados separadamente por **protected
parameters** do Managed Run Command e escritos em arquivo do servidor com modo
600, sob `/opt/ponto-certo/secrets` (700). Não colocá-los no script público, parâmetros
comuns, cloud-init, Terraform, state, imagens, prints ou logs. O cliente de deploy
deve gerar o JSON de parâmetros protegidos em arquivo temporário 600, usar
`az rest --body @arquivo`, evitar impressão do conteúdo e remover o arquivo ao
terminar. Não usar `set -x`. A coleta local de métricas usa Bearer no cabeçalho,
nunca token na URL. Esses fluxos precisam de validação real após provisionamento.

## State e arquivos privados fora do Git

Usar `bash infra/tf.sh ...`. O wrapper configura backend local em
`$HOME/.local/share/ponto-certo/terraform/terraform.tfstate`, `TF_DATA_DIR` e
workspaces também externos. Pasta 700 e arquivos novos 600 (`umask 077`). Um
caminho alternativo em `PC_TERRAFORM_STATE_DIR` deve ser absoluto e externo ao
checkout; o wrapper rejeita caminhos internos. State, planos e `.tfvars` nunca
entram no repositório nem nos artefatos de Actions. O `.terraform.lock.hcl` deve
ser versionado: ele fixa provider e checksums, sem credenciais.

State local é texto sem criptografia nativa do Terraform. Usar FileVault ativo
no Mac (`fdesetup status`) e backup cifrado acessível somente ao operador. Não
afirmar FileVault ativo antes de conferir. O backend usa lock local; há um único
operador de infraestrutura e CI não usa esse state. Para vários operadores,
migrar depois para backend remoto com criptografia, versionamento, IAM e locking,
mantendo backup protegido. Essa migração não está executada.

## Pré-requisitos e confirmação do benefício

Azure for Students concede US$100 por 12 meses sem cartão para estudantes
elegíveis, sujeito à verificação acadêmica. Ao esgotar/expirar crédito, a assinatura
é desabilitada; ela não deve ser convertida para pay-as-you-go para esta entrega.
Não confundir com Azure Students Starter, que tem outro conjunto de serviços.

Pedro precisa ativar/entrar na assinatura acadêmica e concluir a verificação da
instituição. Depois, o operador confere: assinatura Students ativa, saldo suficiente,
validade além da correção, spending limit ativo, permissão de provisionamento e
SKU disponível. Login interativo é feito por Pedro; nunca pedir senha no chat.

Com Azure CLI autenticada no perfil acadêmico, usar comandos de leitura:

```bash
az account show --query '{id:id,name:name,state:state,tenant:tenantId}'
az vm list-skus --location eastus2 --size Standard_B2als_v2 --all \
  --query '[].{name:name,restrictions:restrictions}'
az vm list-usage --location eastus2 --output table
az policy assignment list --query '[].{name:displayName,parameters:parameters}'
az vm image list --location eastus2 --publisher Canonical \
  --offer ubuntu-24_04-lts --sku server --all \
  --query '[-1].{urn:urn,version:version}'
```

Conferir `subscriptionPolicies.spendingLimit` e `quotaId` na API de assinatura,
além do saldo no portal Education/Sponsorships. Nunca remover o limite para vencer
falha de SKU/quota. Políticas podem restringir regiões mesmo quando há saldo.
Se `eastus2`/B2als não puder ser criado, escolher região permitida ou B2s compatível,
refazer estimativa e testar; não contratar máquina maior silenciosamente.

O provider não registra providers Azure automaticamente. Antes do apply, verificar
e, na assinatura acadêmica autorizada, registrar apenas os necessários:
`Microsoft.Compute`, `Microsoft.Network`, `Microsoft.ManagedIdentity`. Isso não
cria serviços de cobrança por si só; os recursos virão do plano Terraform.

## Reprodução

Requer Terraform 1.9+ (<2), Azure CLI, Python 3 e login acadêmico autorizado.
Provider `hashicorp/azurerm` fixado em **5.14.0**. A instalação de ferramentas e
`terraform validate` são locais; `plan` consulta a assinatura e `apply` cria recursos.

Na raiz do repositório:

```bash
umask 077
mkdir -p "$HOME/.local/share/ponto-certo/terraform"
chmod 700 "$HOME/.local/share/ponto-certo/terraform"
bash infra/tf.sh init
bash infra/tf.sh validate
```

Criar uma chave administrativa específica fora do repositório; conservar a parte
privada protegida. A parte pública é o único valor passado para Terraform.
Criar `production.tfvars` no diretório protegido externo com:

```hcl
subscription_id  = "UUID-DA-ASSINATURA-ACADEMICA"
location         = "eastus2"
vm_size          = "Standard_B2als_v2"
public_dns_label = "ponto-certo-fiap-identificador-unico"
admin_public_key = "ssh-ed25519 CHAVE_PUBLICA"
os_image_version = "VERSAO_NUMERICA_VERIFICADA_DA_IMAGEM"
github_repository = "Salvittis/ponto-certo"
github_environment = "production"
```

Os marcadores são exemplos documentais e devem ser substituídos por valores reais.
Imagem `latest` é recusada: a versão numérica verificada torna a recriação auditável.

```bash
bash infra/tf.sh plan \
  -var-file="$HOME/.local/share/ponto-certo/terraform/production.tfvars" \
  -out="$HOME/.local/share/ponto-certo/terraform/approved.plan"
# Revisar assinatura, região, custo, NSG, VM e identidade antes do apply.
bash infra/tf.sh apply "$HOME/.local/share/ponto-certo/terraform/approved.plan"
bash infra/tf.sh output
```

Não publicar o plano/state completo. Registrar evidência sanitizada do apply,
recursos, regras NSG e imagem utilizada. Após o deploy, validar HTTPS, readiness,
pergunta com LLM real, fontes, versão, reinício, métricas e porta 22 fechada. Uma
URL gerada por `output` só é operacional depois do Compose e da emissão do TLS.

## Estimativa de consumo do crédito

Preços Retail API consultados em **19/11/2026**, USD, Linux, `eastus2`, consumo
normal sem Spot/reserva. Estimativa de 8 dias (192 horas), sem assumir franquia:

| Item | Preço de referência | Estimativa 8 dias |
|---|---:|---:|
| B2als_v2, 2 vCPU/4 GiB | US$0,0376/h | US$7,22 |
| Standard SSD E4 LRS 32 GiB | US$2,40/mês | ~US$0,64 |
| IPv4 Standard estático | US$0,005/h | US$0,96 |
| Base estimada | | **~US$8,82 de crédito** |

Operações SSD são US$0,002/10 mil. Tráfego de saída, operações, serviços adicionais
e duração maior alteram o consumo. A estimativa não é gasto realizado nem promessa
de saldo. Com benefício Students ativo e crédito suficiente, a intenção é **R$0
desembolsado**, consumindo crédito educacional. Não ativar modalidade paga. Fonte
de preço vem da API pública Microsoft; não são preços promocionais de terceiros.

Se a conta não tiver benefício elegível, crédito/saldo, permissões ou capacidade,
publicação fica pendente e o trabalho local prossegue. Não migrar para recursos
TBC nem para cobrança sem nova decisão de Pedro.

## Manutenção e término

Manter VM e repositório acessíveis até pelo menos **26/11/2026 às 23h55 de São
Paulo**, confirmando fim da correção antes de encerrar. Não há desligamento
agendado. Conferir saldo e expiração, espaço do disco, CPU credits e alertas. Um
único host é adequado a este MVP acadêmico, sem alta disponibilidade; atualização
de containers pode causar breve interrupção.

Depois da liberação do responsável, guardar PDF/evidências/backup cifrado, revisar
`bash infra/tf.sh plan -destroy -var-file=CAMINHO_EXTERNO` e então executar destroy.
Isso remove URL, VM, disco, IP e identidade. Revogar secrets e a federação de deploy
ao encerrar. Só parar/dealocar a VM deixa disco e IP consumindo crédito; remover os
recursos no encerramento evita custo residual. Não executar limpeza de outros
resource groups ou assinaturas.

## Fontes

- [Azure for Students: requisitos e benefício](https://learn.microsoft.com/azure/education-hub/about-azure-for-students)
- [Esgotamento do crédito Students](https://learn.microsoft.com/azure/cost-management-billing/manage/azurestudents-subscription-disabled)
- [B2als_v2 e CPU credits](https://learn.microsoft.com/azure/virtual-machines/sizes/general-purpose/basv2-series)
- [Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
- [Public IP e DNS fornecido](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses)
- [Managed Run Command](https://learn.microsoft.com/azure/virtual-machines/linux/run-command-managed)
- [OIDC GitHub/Azure](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Permissões Compute](https://learn.microsoft.com/azure/role-based-access-control/permissions/compute)
- [Docker no Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Provider AzureRM](https://registry.terraform.io/providers/hashicorp/azurerm/5.14.0)
- [Backend local e lock](https://developer.hashicorp.com/terraform/language/backend/local)
- [Proteção do state](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)
