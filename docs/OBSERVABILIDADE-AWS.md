# Observabilidade isolada do AWS Academy

Esta configuração acompanha a mesma aplicação/Qwen na EC2 do Sandbox. Não inicia
recursos AWS nem substitui a coleta Azure. A URL e as métricas AWS só podem ser
declaradas validadas depois do deploy, smoke e coleta correspondentes. O encerramento
da sessão apaga os recursos do Sandbox e interrompe o alvo; o tempo de sessão não
é uma franquia financeira.

| Elemento | Azure existente | AWS separado |
|---|---|---|
| Compose | `compose.monitoring.yaml` | [compose.monitoring.aws.yaml](../compose.monitoring.aws.yaml) |
| Projeto | `ponto-certo-monitoring` | `ponto-certo-monitoring-aws` |
| Prometheus local | `127.0.0.1:9090` | `127.0.0.1:9091` |
| Grafana local | `127.0.0.1:3001` | `127.0.0.1:3002` |
| Configuração privada | `.runtime/monitoring` | `$HOME/.local/share/ponto-certo/monitoring-aws` |
| Dados Docker | Volumes do projeto Azure | Volumes prefixados `ponto-certo-monitoring-aws_` |

As duas stacks compartilham somente os arquivos versionados de
[consultas/dashboard](../observability/grafana/dashboards/ponto-certo.json),
[regras](../observability/prometheus/alerts.yaml), blackbox e provisionamento
Grafana, montados somente para leitura. Alvos, tokens, bancos, redes e portas são
separados. Não combinar os dois arquivos Compose com múltiplos `-f`, nem mudar o
nome do projeto AWS para o projeto Azure.

## Preparação e início

Depois de existir uma URL AWS real e o mesmo token estar provisionado no servidor,
execute na raiz do repositório. Substitua o caminho pelo arquivo externo 0600
preparado pelo operador; o comando contém o caminho, nunca o valor do token:

```sh
python3 scripts/configure-monitoring-aws.py \
  --url https://HOST-AWS-REAL \
  --metrics-token-file /CAMINHO-EXTERNO/aws-metrics-token

export PC_AWS_MONITORING_DIR="$HOME/.local/share/ponto-certo/monitoring-aws"
docker compose -f compose.monitoring.aws.yaml config --quiet
docker compose -f compose.monitoring.aws.yaml up -d --force-recreate
```

O [configurador AWS](../scripts/configure-monitoring-aws.py) não acessa a rede nem
inicia containers. Exige origem HTTPS pública, arquivo de credencial do operador
sem acesso de grupo/outros e diretório absoluto fora do Git. Não lê `METRICS_TOKEN`
do ambiente para evitar reutilização acidental da credencial Azure. O arquivo
original permanece 0600; cópias para montagem são 0444 dentro de diretório 0700,
permitindo leitura pelos containers não root sem permitir que outros usuários
do host atravessem o diretório. A senha Grafana é gerada separadamente, preservada
nas reexecuções e nunca impressa. Consulte-a apenas pelo mecanismo privado do
operador, sem salvá-la em evidências.

As gravações são atômicas; por isso, recriar somente os containers AWS após
reconfigurar garante que os bind mounts usem os arquivos novos. A opção
`--force-recreate` preserva os volumes e o histórico do Prometheus/Grafana.

Abra `http://127.0.0.1:3002/d/ponto-certo-golden-signals` e use usuário `admin`.
Prometheus fica em `http://127.0.0.1:9091`; blackbox não publica porta no host.
Interfaces administrativas são locais, não acessíveis por `0.0.0.0`. A retenção
é 10 dias ou 512 MB. O computador precisa permanecer ativo para coletar.

## Coleta e interpretação

O [coletor existente](../scripts/collect-cloud-evidence.py) já é genérico para
HTTPS/Prometheus. Use a porta AWS e um arquivo próprio, sem flags Azure:

```sh
python3 scripts/collect-cloud-evidence.py \
  --public-url https://HOST-AWS-REAL \
  --prometheus-url http://127.0.0.1:9091 \
  --expect-revision SHA-COMPLETO-DO-DEPLOY \
  --output evidencias/cloud/aws/observability-baseline.json
```

O comando acima só consulta; não gera tráfego nem interrompe/reinicia serviços.
Ele não lê token, exige dois alvos públicos correspondentes à URL e verifica o
histórico de dez minutos para impedir atribuição de séries locais/Azure ou de um
endereço anterior. Quando há mistura, os valores ficam nulos, o escopo vira
`configuration` e a saída é não zero. Não contornar essa guarda.

As quatro métricas mantêm as definições de [OBSERVABILIDADE.md](OBSERVABILIDADE.md):
p95 HTTP aproximado por buckets e taxa de perguntas/erros em janela de cinco
minutos; saturação representa ocupação instantânea do slot LLM, não CPU/RAM.
Registrar URL, revisão, horário, unidade e janela. Tráfego demonstrativo, falha e
recuperação devem ocorrer na EC2 monitorada. Screenshots e JSON Azure existentes
não comprovam execução AWS.

Para runtime, reutilizar `GUEST_SCRIPT` e `clean_containers` desse mesmo coletor:
o operador pode enviar o script sem segredos por SSM `AWS-RunShellScript` à
instância AWS previamente conferida e sanitizar o JSON com
`clean_containers(body, 'public')`. Essa inspeção lê usuários efetivos, configurações
permitidas, `docker stats`, `/proc/meminfo` e SHA/tamanho dos pesos; não imprime
Env, logs ou perguntas e não reinicia containers. O modo automático
`--azure-resource-group/--azure-vm` é exclusivo da Azure e não deve ser usado para
AWS. Confirmar status/exit code da execução SSM, conservar o escopo AWS em arquivo
próprio e nunca tratar inspeção com erro como sucesso.

## Outra sessão ou encerramento

Um novo IP do Sandbox é outro alvo. O configurador recusa trocar a URL por padrão;
`--replace-target` autoriza explicitamente alterar somente o monitor AWS, mas não
apaga o histórico. Após mudança, esperar a janela histórica deixar de conter o
alvo antigo antes de usar métricas como evidência. Para uma sessão com banco novo,
preservar as evidências e planejar a limpeza **somente dos volumes AWS**; o
configurador não os remove automaticamente.

Depois de preservar JSON e capturas, pare somente a stack AWS quando o Sandbox
encerrar:

```sh
PC_AWS_MONITORING_DIR="$HOME/.local/share/ponto-certo/monitoring-aws" \
  docker compose -f compose.monitoring.aws.yaml stop
```

Não declarar a URL AWS disponível após apagar o laboratório. Azure continua com
seu próprio ciclo de disponibilidade, monitoramento e evidências.
