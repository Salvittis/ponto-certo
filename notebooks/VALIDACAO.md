# Validação do notebook

Executado em 19/11/2026 com o Python 3.12 do projeto e dependências de `notebooks/requirements.txt`.

- `avaliacao-ia.ipynb`: seis células de código executadas em ordem 1–6, 17 saídas salvas, zero saídas de erro; estrutura validada com `nbformat.validate`.
- As saídas são calculadas dos JSON versionados de `avaliacao/runs/test-v1` e `base/retrieval_results.json`. A construção do notebook não repetiu inferência nem alterou o experimento.
- O gráfico `placar.png` foi aberto e inspecionado visualmente: valores, legendas, eixos, rótulos e títulos legíveis e coerentes com o placar automático. Os dois painéis mostram medidas distintas, ambas com denominador de 24 casos.
- Exportação HTML concluída em `avaliacao-ia.html`. A tentativa de revisão do HTML renderizado encontrou indisponibilidade do navegador integrado e inventário de navegadores vazio no ambiente do agente. Portanto a leitura completa do HTML em navegador não foi validada; a figura foi verificada separadamente.

Para reproduzir a construção e execução, a partir da raiz:

```sh
python -m pip install -r notebooks/requirements.txt
python notebooks/build_notebook.py --run avaliacao/runs/test-v1
```

Para repetir somente a execução do notebook existente:

```sh
python -m jupyter nbconvert --execute --to notebook --inplace notebooks/avaliacao-ia.ipynb
```

Para conferir a apresentação completa, abrir o notebook no Jupyter/VS Code/GitHub, ou abrir o HTML no navegador. A validade do experimento de conteúdo não depende do visualizador. A latência registrada é exploratória: houve uma consulta UI concorrente no início do teste e aquecimento de cache.
