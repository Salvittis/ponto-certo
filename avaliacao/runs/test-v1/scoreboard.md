# Placar automático

Acerto por propriedades é proxy automático, não acurácia semântica plena. Candidatos a afirmação proibida exigem auditoria. JSON final pode refletir validação/fallback do servidor; JSON bruto mede geração.

| Configuração | Casos | Acerto por propriedades | Status | JSON final | Fontes exigidas presentes | Recusa/status negativo | JSON bruto / chamadas LLM | Latência média (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 24 | 9/24 | 11/24 | 24/24 | 0/9 | 8/14 | 24/24 | 0.72 |
| rag | 24 | 12/24 | 15/24 | 24/24 | 9/9 | 9/14 | 24/24 | 0.921 |
| agent | 24 | 15/24 | 15/24 | 24/24 | 4/9 | 11/14 | 17/17 | 0.898 |
