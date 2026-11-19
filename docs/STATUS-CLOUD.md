# Estado Cloud - Ponto Certo

Atualizado em 19/11/2026. Documento de trabalho; configuração não equivale a publicação validada.

## Escopo e decisões

- Mesma aplicação FastAPI/LLM da entrega IA, no mesmo repositório `ponto-certo/`.
- IA mantém app, base, avaliação, README e contrato funcional; Cloud mantém Docker/Compose, Terraform, pipeline, observabilidade e PDF.
- O PDF oficial p.52-53 exige deploy blindado, quatro scanners/etapas, Terraform, métricas e alerta disparado. Divergências institucionais: regra geral 10 pontos/Teams (p.24), Cloud 14 pontos/portal (p.52-53). Submissão fica com Pedro/equipe.
- Três containers não root em produção: proxy HTTPS, API e LLM privada. Modelo Qwen2.5-1.5B Q4_K_M, pesos fixados por revisão/SHA e embutidos na imagem. Sem dependência de download após reinício, sem volume de dados pessoais.
- Provedor não determinado pelo PDF. Railway autenticado foi consultado somente em leitura. Pedro informou que é ambiente da TBC e pediu separação: **não criar ou alterar recursos nesse ambiente**.
- Pedro ativou Azure for Students: US$100 disponíveis e spending limit ativo, verificados em 19/11. Objetivo: nenhum desembolso; não converter para assinatura paga. Brasil Sul e Canadá Central restringiram os tamanhos de VM consultados. Chile Central foi selecionado após verificar disponibilidade e quota. Terraform criou 12 recursos, incluindo VM B2als_v2 de 2 vCPU/4 GiB. Estimativa base: US$13,45 de crédito por nove dias; tráfego e operações de disco variam.
- AWS Academy foi sugerida por Pedro como alternativa em paralelo. Acesso ao laboratório ainda não iniciado; duração de sessão e parada de EC2 precisam ser conferidas antes de considerá-lo hospedagem contínua até 27/11.

## Preparação

- Contrato integrado em `docs/CONTRATO-IA-CLOUD.md`; mesma API, modelo, pesos e base da IA. Dados de transporte no modo demo são sintéticos; inferência da LLM é real.
- Docker Compose local subiu saudável. Smoke real validou pergunta documental (7,974 s) e previsão demonstrativa (4,705 s), com fontes. Evidência: `evidencias/cloud/smoke-compose.json`.
- Imagens locais ARM64 da API Alpine e LLM passaram Trivy sem HIGH/CRITICAL e sem segredos. A verificação Linux/AMD64 no GitHub permanece obrigatória e independente.
- Primeiro push público: `6cdcb491ff091d9fdf8b87592d7e847ed674877a`. Run [44515603367](https://github.com/Salvittis/ponto-certo/actions/runs/44515603367) foi efetivamente barrado: Semgrep detectou `eval` no arquivo sintético isolado; Trivy encontrou problemas reais na base Debian da API e no proxy Caddy. Publicação e deploy ficaram skipped. Gitleaks, testes e Trivy da LLM passaram.
- Correções preparadas: remoção do caso sintético, API em Alpine atualizada e Caddy recompilado com dependências corrigidas e travadas. Nenhum scanner foi desativado e nenhuma vulnerabilidade foi suprimida. Próximo run ainda pendente.
- Terraform Azure validado com estado/tfvars fora do repositório, entrada somente 80/443 e identidade OIDC para GitHub. Plano revisado e apply concluído: 12 criações, nenhuma alteração/destruição. A identidade OIDC tem escopo somente nesta VM; environment GitHub production aceita somente main e já recebeu Secrets/Variables.
- Prometheus/Grafana local monitorando a URL pública será usado conforme permissão expressa da p.53.
- Prometheus, regras de alerta e dashboard de quatro métricas passaram validações estáticas. Dashboard com tráfego público, alerta disparado e recuperação ainda pendentes.
- A infraestrutura está provisionada; URL de destino https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com. Ainda não existem publicação validada, pipeline aprovado com deploy ou alerta público disparado. Evidência de bloqueio já existe.

## Dependências reais

1. Confirmar bootstrap da VM e acompanhar a publicação automática do commit corrigido.
2. Executar pipeline corrigido, publicar e validar a mesma aplicação final da IA, incluindo métricas protegidas e revisão do commit exposta.
3. Token SPTrans para validação ao vivo. Sem token, o modo demo é sintético e deve permanecer claramente identificado.
4. Gerar evidências públicas e PDF único conferido visualmente. Nomes e RMs reais já constam na Ficha Técnica compartilhada.

## Evidências

- Testes corrigidos: 54 passaram localmente (19 IA/API e 35 deploy/segurança operacional). Smoke após hardening passou com inferência real em Compose. Esses resultados locais não substituem a verificação pública.

Somente acrescentar resultados realizados com data, comando/run, commit e limites. Artefatos públicos deverão ser sanitizados; `.env`, tokens, state e `.tfvars` permanecem fora do Git.
