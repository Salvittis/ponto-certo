# SPTrans ao vivo — verificação de 19/11/2026

Adendo operacional à entrega de IA. **A autenticação e consultas reais à SPTrans foram verificadas; o aplicativo público permanece em modo DEMO até Cloud validar a integração no ambiente publicado e efetuar a troca.** Este registro não modifica o corpus nem a avaliação A/B/C original, que usou dados sintéticos.

A conta e o aplicativo **Ponto Certo - FIAP CitizenTech** foram cadastrados pelo fluxo oficial, com a chave indicada como homologada/em uso. O segredo foi guardado no `.env` local, ignorado pelo Git e com permissão `0600`; seu valor não integra este documento nem a evidência publicada. O cadastro da chave, isoladamente, não prova autenticação: a confirmação abaixo vem da resposta real da API.

## Evidência observada

Em **19/11/2026, 09:54:24–09:54:25 (America/Sao_Paulo)**, o [verificador](../scripts/verify_sptrans.py) realizou seis requisições HTTPS: autenticação, busca de linhas e duas sequências de busca de paradas/previsão. A API retornou `true` na autenticação. [JSON sanitizado da verificação](../evidencias/sptrans-verificacao-20261119T125425332800Z.json).

A busca por `8000` retornou **quatro registros de linha**. O script selecionou o primeiro serviço na ordenação e até dois sentidos distintos: `lt=8000`, `tl=1`, registrado como `8000-1`. Essa representação preserva o retorno observado; não deve ser substituída pelos códigos ou pelo serviço da demonstração sintética.

| Consulta | Linha/sentido descobertos | Paradas retornadas | Ponto selecionado | Resultado de previsão |
|---|---|---:|---|---|
| 1 | Código **2506**, sentido **1**, serviço **1** | 14 | **7014417 — ANGELICA B/C** | Consulta bem-sucedida, **retorno vazio** |
| 2 | Código **35274**, sentido **2**, serviço **1** | 13 | **614432 — BABY BARIONY C/B** | Consulta bem-sucedida, **uma previsão**, horário retornado **10:05** |

**Somente uma das duas consultas retornou previsão.** Não houve previsão nos dois sentidos. O retorno vazio da primeira consulta não comprova falta de ônibus, suspensão da linha ou ausência de serviço.

A fonte informou `hr=09:54`; a data não vem nesse campo e foi inferida pelo dia mais próximo da consulta. A idade calculada desse relógio foi 25 segundos. Na única previsão recebida, a observação do veículo era de 09:54:15, com idade de dez segundos. Esses valores descrevem **aquela consulta histórica**, não uma chegada atual nem garantia de cumprimento. O JSON preserva horários e códigos públicos de linha/parada, sem coordenadas, identificadores de veículos, token, cookies ou corpo bruto da resposta.

A amostra foi limitada a uma parada por sentido, escolhida pelo menor código retornado, sem varredura ampla. Ela confirma acesso e existência de resposta nesse recorte e instante; não comprova cobertura de toda a linha ou do município.

## Repetir com segurança

Depois de configurar `SPTRANS_TOKEN` no mecanismo de segredos do servidor ou no `.env` local protegido, sem inserir o valor na linha de comando:

```sh
.venv/bin/python -m scripts.verify_sptrans --query 8000
```

O script autentica de verdade, descobre os códigos a partir do retorno, limita a execução a seis requisições e salva uma nova evidência sanitizada com data/hora. A presença de um token, `DATA_MODE=live` ou uma resposta positiva de `/readyz` **não substitui esse teste de autenticação e consulta**. A prontidão da aplicação verifica configuração/modelo; não demonstra, por si, acesso real à SPTrans.

O próximo passo é fornecer o segredo a Cloud por canal próprio para credenciais, validar consultas reais no runtime publicado junto à LLM e conferir a jornada completa, fontes e atualização. Somente depois alterar o aplicativo público para `live` e registrar uma nova evidência. Até lá, os avisos de simulação da interface continuam corretos.

## Condições oficiais consultadas

As [Condições de Acesso do cadastro de desenvolvedor](https://www.sptrans.com.br/desenvolvedores/cadastro-desenvolvedores/registro-desenvolvedores-pf/) informam cadastro e dados gratuitos; proíbem alugar, sublicenciar ou vender os dados e não garantem completude, ausência de erros ou disponibilidade contínua. Não foi identificada licença padronizada como Creative Commons. Estas condições complementam a pesquisa anterior, sem alterar retroativamente os arquivos congelados da avaliação.

O [guia oficial](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/) descreve confirmação de cadastro por e-mail e criação do aplicativo em “Meus Aplicativos”. A [referência da API](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/) documenta autenticação e consultas, exige HTTPS e alerta para a cobertura limitada da categoria de paradas.
