# Avaliação reproduzível

O conjunto `dev.jsonl` é usado para ajustes. `test.jsonl` foi escrito antes da primeira execução e seu SHA-256 está em `freeze.json`. Não usar o conjunto final para escolher limiar/prompt. As perguntas individuais são entradas do experimento; o gabarito não entra no contexto do modelo.

Três configurações: `baseline` (mesmo modelo sem contexto), `rag` (recuperação documental) e `agent` (recuperação + consultas controladas). É uma interpretação conjunta do objetivo e da rubrica, não enumeração literal do PDF.

## Execução

Com o servidor da LLM local configurado como no README principal:

```sh
python -m avaliacao.run --split dev --output avaliacao/runs/dev-v1
python -m avaliacao.run --split test --output avaliacao/runs/test-v1
```

O runner nunca sobrescreve um diretório de execução. Salva entrada, saída integral, saída bruta do modelo quando disponível, tempo, verificações, hashes do código/base, ambiente não secreto e placar. Não passa cenários ou gabaritos como instruções ao modelo. As configurações são sequenciais por caso para evitar concorrência de inferência. Manter os mesmos parâmetros de geração, modelo e fixtures.

## Medidas e denominadores

- **Recall@k exigido pelo PDF:** média, entre perguntas documentais respondíveis, de `|relevantes ∩ top-k| / |relevantes|`. Reportar também hit@k se calculado; não confundir as medidas quando há mais de um trecho relevante. Sem resposta: avaliar rejeição abaixo do limiar separadamente, fora do denominador de recall.
- **Limiar:** escolher em `base/retrieval_dev.jsonl`, documentar grade e objetivo (responder quando há evidência/rejeitar negativos); aplicar uma única vez a `retrieval_test.jsonl` sem reajuste.
- **Acerto por propriedades (escolha do projeto):** esquema final válido, status aceito, grupos de fatos obrigatórios presentes, sem candidatos a afirmações proibidas e fonte presente quando exigida. É um proxy conservador e dependente das propriedades escolhidas; não substitui julgamento semântico.
- **Status correto:** uma das respostas de estado aceitas pelo gabarito. “Não consta”, esclarecimento e indisponibilidade são diferentes.
- **Alucinação:** afirmação factual não apoiada nas evidências permitidas. Será auditada a partir de saídas salvas. JSON inválido, omissão e recusa excessiva são erros, mas não necessariamente alucinações. Regex apenas levanta candidatos; não é contagem final de alucinações.
- **JSON:** validade do esquema final por caso; separadamente JSON bruto válido por chamada da LLM. Um fallback pode garantir JSON final sem demonstrar competência de formatação do modelo.
- **Fontes:** presença de ID/URL por caso respondível que exige fonte; conferir sustentação em auditoria. Link presente não prova sustentação.
- **Recusa/estado negativo:** status aceito nos casos em que o gabarito não aceita `ok`, incluindo falta de informação, necessidade de esclarecimento e indisponibilidade. Reportar falso negativo nas perguntas respondíveis por meio dos erros.
- **Latência:** tempo de parede local por configuração; não é SLA nem previsão de desempenho na nuvem.

## Limites

24 casos finais e 6 de desenvolvimento são amostra pequena escrita para cobrir riscos, não uma amostra probabilística de passageiros. Casos dinâmicos são **sintéticos**, com estrutura inspirada no contrato público da API. Não são capturas reais nem demonstram cobertura atual da SPTrans. A integração ao vivo é evidência separada e permanece dependente de acesso validado. A comparação mede o sistema completo; ganhos do agente podem vir de ferramentas e guardrails determinísticos, e não de alteração dos pesos da LLM. Teste cego só vale antes de observar as saídas; ajustes posteriores precisam ser apresentados como regressão, preservando o primeiro resultado.

## Resultados preservados

- `runs/dev-v1/`: primeiro experimento de desenvolvimento, 6 casos por configuração.
- `runs/test-v1/`: teste final de 24 casos por configuração; código/base inalterados durante execução.
- `runs/test-v1/scoreboard.md`: placar por propriedades; `audit.md` e `audit.json`: revisão qualitativa das 72 saídas finais/65 brutas e cinco erros reais.
- `retrieval-audit.json`: reprodução independente dos valores canônicos de `base/retrieval_results.json`.
- `../notebooks/avaliacao-ia.ipynb`: notebook executado com saídas salvas; `../notebooks/VALIDACAO.md` registra a cobertura da verificação.

A auditoria identificou dois falsos positivos do proxy em RAG (T04/T10), sem editar gabarito ou resultado automático depois de observar respostas. Os ajustes propostos permanecem propostas; não foram usados para reclassificar o experimento como um novo teste cego.
