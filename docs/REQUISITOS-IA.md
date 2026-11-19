# Ponto Certo — requisitos verificados de IA

Fonte normativa: PDF original `Desafio-FIAP-GS-CitizenTech 4ES.pdf`, 60 páginas, preservado na pasta superior. Conferência em 19/11/2026. A matriz distingue obrigações acadêmicas, escolhas do produto e pendências. Não equivale a aprovação ou nota atribuída pelo professor.

## Exigências explícitas do PDF

| Página | Exigência | Evidência da entrega a conferir |
|---|---|---|
| 18 | Um mesmo produto nas sete disciplinas; MVP funcional/navegável; dados reais ou simulados com geração justificada | Aplicação Ponto Certo; fixtures claramente rotuladas |
| 20 | Ficha Técnica abre README principal e documentação da disciplina | README e relatório de IA |
| 21 | Credenciais protegidas; minimização de dados; acessibilidade; resiliência; IA responsável; integração real; reprodução | API, interface, testes e contrato Cloud |
| 24–25 | Até cinco alunos da mesma turma; um integrante envia; 19/11 às 23h55; links públicos funcionando durante correção por até uma semana | Responsabilidade da equipe; verificar URLs públicas |
| 29 | LLM local; mobilidade/energia/segurança; comparar com mesmo modelo sem contexto; integrar ao produto com segurança, explicabilidade e LGPD | Modelo local, experimento e API |
| 29–31 | Repositório público GitHub com notebooks e saídas, base, testes, API, README; relatório no GitHub | Pastas e relatório versionados; publicação verificável |
| 30 | Tarefa + gabarito, inclusive “não consta” (0,5) | `avaliacao/dev.jsonl`, `test.jsonl` |
| 30 | Trechos com fonte (1,0) | `base/` |
| 30 | Recall@1, recall@3 e limiar justificado (1,0) | `avaliacao/retrieval.json` e metodologia |
| 30 | Geração fundamentada, JSON válido, citação e recusa (2,0) | Respostas brutas e finais salvas |
| 30 | Especialização LoRA **ou agente**, comparada ao RAG simples (2,0) | A/B/C com mesmo modelo |
| 30 | Placar de três configurações interpretado (2,0) | Métricas calculadas, limitações e relatório |
| 30 | Cinco erros reais e correções propostas (1,0) | Respostas observadas, esperado, causa provável e proposta |
| 30 | README e reprodutibilidade (0,5) | Comandos executáveis e versões |
| 31 | Nomes completos/RMs; Ficha; diagrama; tabela de fontes, formato, licença e trechos; desempenho; cinco erros; conclusão; repo e vídeo | Relatório de IA |
| 14 | Identificar ODS e explicar contribuição às metas | ODS 11; contribuição como proposta, sem impacto medido inventado |
| 51–53 | Cloud publica o mesmo MVP com Docker, Terraform, CI/CD, scanners, monitoramento, URL e relatório PDF | Frente Cloud, fora da implementação desta frente IA |

## Decisões confirmadas por Pedro no pedido atual

Ponto Certo atende quem depende de ônibus municipais de São Paulo; explica linhas, rotas/espera com informação confiável. Fonte principal proposta: SPTrans Olho Vivo; Pedro/Salvitti responde por IA e Cloud, com dois agentes coordenados. Componentes Visão Computacional, sensor PIR e RPA são dependências de contexto, sem implementação assumida por IA. Reduzir incerteza é o benefício demonstrável; reduzir efetivamente a espera exige estudo posterior.

## Interpretações e escolhas técnicas

- O título e o objetivo usam “treinamento”, mas a rubrica aceita “LoRA ou agente”. Especialização por agente de consultas controladas é admissível como interpretação da rubrica; não afirmar que houve ajuste de pesos.
- O PDF pede três configurações sem listá-las. A = mesmo modelo sem contexto; B = RAG simples; C = RAG + agente é interpretação conjunta do objetivo e da rubrica.
- Interface web mínima faz parte da organização pedida por Pedro, não uma tecnologia obrigatória do PDF.
- Por ausência de acesso ao vivo confirmado na preparação, as comparações dinâmicas usam cenários sintéticos versionados, explicitamente identificados. Não chamar esses cenários de capturas reais.
- Métricas de acerto, fonte, JSON e recusa operacionalizam a avaliação além de recall@1/@3 explicitamente exigidos. Nenhuma métrica automática isolada prova ausência de alucinação.
- O relatório de IA pode ser Markdown no GitHub. PDF é requisito específico de Cloud, não obrigatório para IA. Vídeo é exigido por link; a seção IA não fixa duração ou plataforma.

## Divergências registradas

O resumo encaminhado e as páginas 28–31 concordam na pontuação de IA: 10 pontos. A regra geral da p24 fala em 10 pontos por disciplina e Teams. Cloud p52–53 detalha 14 pontos e “portal da disciplina”, com PDF. A divergência pertence à frente Cloud e deve ser exposta à equipe; não altera os critérios de IA nem autoriza prorrogação.

## Informações ainda não confirmadas

Nomes completos e RMs foram fornecidos por Pedro e constam no relatório. Permanecem sem confirmação nesta etapa: acesso/token autorizado SPTrans; cobertura real de linhas/sentidos/paradas da conta; URL pública e integração completa em Cloud; URL pública do vídeo; envio acadêmico. Recursos observados, licença e hash do modelo devem ser preenchidos após execução. A ficha histórica do Brain era anterior ao pedido atual e não limita a implementação agora expressamente autorizada.
