# Deploy AWS Academy durante uma sessão ativa

O job `deploy_aws` é irmão do deploy Azure e depende da mesma publicação aprovada.
Somente push em `main` com a Variable **do repositório** `AWS_ENABLED=true` habilita
AWS. A flag não condiciona o job Azure, não renova credenciais e não ignora gates.
Desative-a ao encerrar o Lab. `workflow_dispatch` continua sem publicação/deploy,
como no fluxo original; para uma nova entrega, use um push em main com gates completos.

Configure o environment `aws-academy`:

- Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`,
  `AWS_METRICS_TOKEN` próprio deste ambiente; `AWS_SPTRANS_TOKEN` somente para live.
- Variables: `AWS_EXPECTED_ACCOUNT_ID`, `AWS_REGION`, `AWS_INSTANCE_ID`,
  `AWS_PUBLIC_URL`; `AWS_DATA_MODE` assume demo.
- `AWS_SESSION_VALID_UNTIL` é opcional, em ISO-8601 com timezone. Quando informado,
  deve deixar pelo menos 45 minutos ao iniciar o job. É uma janela operacional
  declarada, não uma garantia de validade futura do token. Sem esse dado, a
  evidência registra `session_valid_until: null`; STS valida as credenciais atuais.

O role/profile existente do Lab deve permitir SSM e leitura SecureString na EC2.
O principal do pipeline precisa consultar conta/instância/SSM, criar/excluir o
parâmetro temporário e enviar/consultar comandos. Não criamos IAM, OIDC, keypair
ou permissões novas. Antes de qualquer escrita são conferidos conta esperada,
instance ID exato, tag `project=ponto-certo`, arquitetura amd64, estado running,
profile presente e SSM Online. A EC2 precisa do bootstrap `bootstrap-ready.txt`,
AWS CLI e Docker Compose, conforme `infra/aws`.

Os segredos entram exclusivamente em um SecureString **Standard**, `DataType=text`,
com a chave padrão `alias/aws/ssm`. O JSON é limitado a 4 KiB, sem upgrade automático.
O AWS CLI recebe um arquivo temporário 0600; valores não entram em argumentos,
SendCommand, Terraform state, user data, Git ou outputs do GitHub. O comando contém
somente conteúdo público e o nome/version do parâmetro; a EC2 o lê pelo seu profile.
O GITHUB_TOKEN do próprio job tem apenas packages:read. `release.sh` usa login por
stdin, DOCKER_CONFIG temporário 0700 e remove esse arquivo após pull ou erro.
METRICS_TOKEN permanece no runtime.env 0600 necessário à aplicação; o token GHCR
nunca é salvo nesse arquivo nem em snapshots de rollback.

O runner exclui o SecureString em `finally` depois do comando, incluindo falhas.
Falha de exclusão torna o job vermelho e fica registrada. Cancelamento abrupto,
indisponibilidade ou expiração podem impedir essa exclusão; nesse caso a limpeza
de `/ponto-certo/ci/` precisa ser confirmada na sessão seguinte. Standard não tem
TTL automático. O token GHCR é temporário e não se torna uma credencial permanente.

SSM só passa com `Status=Success` e `ResponseCode=0`; `InvocationDoesNotExist`
transitório é tolerado durante polling. O runner verifica HTTPS/revisão/readiness
e smoke real. Falha pública pede rollback com a mesma guarda de revisão do Azure.
Expiração no meio da operação é falha, nunca prova de deploy ou recuperação.
Relatórios AWS usam nomes próprios, sem sobrescrever evidências Azure.

Fontes: [AWS SecureString em Run Command](https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-param-runcommand.html),
[criptografia KMS](https://docs.aws.amazon.com/systems-manager/latest/userguide/secure-string-parameter-kms-encryption.html),
[credenciais temporárias](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_use-resources.html),
[status SSM](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html).
