# Base documental do Ponto Certo

A base contém **18 trechos**, em JSONL UTF-8, produzidos em **19/11/2026**. Cada linha inclui `id`, `title`, `text`, `source_url`, `source_title`, `retrieved_at`, `kind` e `license`. `manifest.json` registra origem, contagem e hash SHA-256. Não há dados pessoais, capturas de previsão ou GTFS indexados.

| Fonte | Formato original | Trechos | Condições verificadas |
|---|---|---:|---|
| [Documentação Olho Vivo](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api) | HTML | 9 | Página pública; licença específica de reutilização não localizada. API exige cadastro/token. Sínteses curtas, sem cópia integral. |
| [Área do Desenvolvedor SPTrans](https://www.sptrans.com.br/desenvolvedores) | HTML | 1 | Página pública; licença específica não localizada. Nenhum arquivo GTFS foi obtido. |
| [Política do produto](POLITICA-DO-PRODUTO.md) | Markdown autoral | 8 | Regras definidas para o projeto, explicitamente separadas das afirmações oficiais. Licença final acompanha o repositório. |

Os trechos D01–D10 são sínteses documentais; P01–P08 são decisões e limites do Ponto Certo. As condições não identificadas não foram convertidas em uma licença inventada. A reportagem contextualiza o problema no relatório, mas não integra este corpus técnico.

## Recuperação e reprodução

```sh
python -m base.evaluate_retrieval
```

Executar na raiz do repositório. A implementação usa apenas a biblioteca padrão do Python. O índice é reconstruído a partir de título e texto: remoção de acentos, minúsculas, stopwords, TF sublinear, IDF suavizado e cosseno. Empates são ordenados por ID. Não há embeddings remotos.

`Retriever(threshold=0.12)` mantém o valor inicial de engenharia. Para reproduzir a calibração executada, use `Retriever(threshold=0.05)`. `rank(question, k)` devolve os melhores trechos antes do limiar; `search(question, k)` devolve somente trechos com escore positivo que passam o limiar. Ambos retornam os metadados do trecho e `score`. O escore não é probabilidade de resposta correta.

## Separação entre ajuste e avaliação

`retrieval_dev.jsonl` contém 14 perguntas respondíveis e quatro sem resposta. `retrieval_test.jsonl` contém outras 14 respondíveis e quatro sem resposta. Os arquivos foram escritos e tiveram os hashes registrados em `retrieval_split_manifest.json` antes da primeira execução. Cada gabarito aponta para o ID da evidência. Corpus, tokenização e teste não foram modificados em função dos resultados.

O limiar foi escolhido **somente no dev**, em uma grade de 0,05 a 0,50 com passo 0,01, maximizando a média da taxa de aceitação das perguntas respondíveis e da taxa de rejeição das perguntas sem resposta. Critérios de desempate: maior recall@3 após limiar, depois menor limiar. O valor selecionado foi **0,05**. A regra favorece retenção de evidência em empate; o agente e a validação da resposta devem decidir se os trechos realmente sustentam a afirmação.

`recall@k = média(|relevantes ∩ top-k| / |relevantes|)` nas perguntas respondíveis. Como cada questão deste conjunto tem uma evidência suficiente, o valor coincide com a taxa de acerto do trecho. Perguntas sem resposta não têm denominador de recall e são avaliadas pela rejeição.

| Medida no teste congelado | Resultado |
|---|---:|
| Recall@1, antes do limiar | 13/14 = 92,86% |
| Recall@3, antes do limiar | 14/14 = 100% |
| Recall@3, após o limiar | 14/14 = 100% |
| Rejeição das perguntas sem resposta | 4/4 = 100% |

Os resultados e a grade completa estão em `retrieval_results.json`. O conjunto é pequeno e autoral; as negativas são lexicais relativamente fáceis. Não se pode generalizar estes números para o uso público ou concluir que o limiar resolve perguntas sem resposta próximas ao tema. Uma palavra compartilhada pode produzir similaridade sem evidência suficiente; geração e recusa exigem validação própria. A busca documental não determina o tempo de espera nem substitui consulta dinâmica.
