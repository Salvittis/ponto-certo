# Placar automático

Acerto por propriedades é proxy automático, não acurácia semântica plena. Candidatos a afirmação proibida exigem auditoria. JSON final pode refletir validação/fallback do servidor; JSON bruto mede geração.

| Configuração | Casos | Acerto por propriedades | Status | JSON final | Fontes exigidas presentes | Recusa/status negativo | JSON bruto / chamadas LLM | Latência média (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 6 | 1/6 | 3/6 | 6/6 | 0/3 | 1/3 | 6/6 | 1.008 |
| rag | 6 | 3/6 | 4/6 | 6/6 | 3/3 | 1/3 | 6/6 | 1.223 |
| agent | 6 | 6/6 | 6/6 | 6/6 | 3/3 | 3/3 | 3/3 | 0.97 |
