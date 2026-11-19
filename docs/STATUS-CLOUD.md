# Estado Cloud - Ponto Certo

Atualizado em 19/11/2026. Documento de trabalho; configuração não equivale a publicação validada.

## Escopo e decisões

- Mesma aplicação FastAPI/LLM da entrega IA, no mesmo repositório `ponto-certo/`.
- IA mantém app, base, avaliação, README e contrato funcional; Cloud mantém Docker/Compose, Terraform, pipeline, observabilidade e PDF.
- O PDF oficial p.52-53 exige deploy blindado, quatro scanners/etapas, Terraform, métricas e alerta disparado. Divergências institucionais: regra geral 10 pontos/Teams (p.24), Cloud 14 pontos/portal (p.52-53). Submissão fica com Pedro/equipe.
- Dois containers não root: app pública e LLM privada. Modelo Qwen2.5-1.5B Q4_K_M, pesos fixados por revisão/SHA e embutidos na imagem. Sem dependência de download após reinício, sem volume de dados pessoais.
- Provedor não determinado pelo PDF. Railway autenticado foi consultado somente em leitura. Pedro informou que é ambiente da TBC e pediu separação: **não criar ou alterar recursos nesse ambiente**. Conta pessoal/provedor e teto de gasto aguardam definição.

## Preparação

- Contrato inicial recebido em `docs/CONTRATO-IA-CLOUD.md`.
- Dockerfiles e Compose em elaboração/teste; pipeline e Terraform em elaboração.
- Prometheus/Grafana local monitorando a URL pública será usado conforme permissão expressa da p.53.
- Não existem ainda URL publicada, provisionamento executado, evidência de pipeline aprovado/barrado ou alerta de produção disparado.

## Dependências reais

1. Conta pessoal de nuvem e limite de gasto, separados da TBC.
2. Aplicação final e modelo avaliados pelo agente IA; integração de métricas protegidas e revisão do commit exposta.
3. Token SPTrans para validação ao vivo. Sem token, o modo demo é sintético e deve permanecer claramente identificado.
4. Nomes completos e RMs reais da equipe (coleta coordenada com IA).

## Evidências

Somente acrescentar resultados realizados com data, comando/run, commit e limites. Artefatos públicos deverão ser sanitizados; `.env`, tokens, state e `.tfvars` permanecem fora do Git.
