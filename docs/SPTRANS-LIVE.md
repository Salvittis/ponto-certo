# SPTrans ao vivo — verificação de 19/11/2026

Adendo operacional à entrega de IA. **A aplicação pública [Azure](https://ponto-certo-fiap-rm88166.chilecentral.cloudapp.azure.com) está com LIVE confirmado por HTTP e formulário real em 19/11/2026, às 11:03–11:06 (America/Sao_Paulo), na revisão `8b1e298a101eb9b90bf723efad268449381e2552`.** O AWS Sandbox permanece DEMO. Os registros abaixo são evidências históricas, sem garantia de chegada ou disponibilidade futura. Este adendo não modifica o corpus nem a avaliação A/B/C original, que usou dados sintéticos.

A conta e o aplicativo **Ponto Certo - FIAP CitizenTech** foram cadastrados pelo fluxo oficial, com a chave indicada como homologada/em uso. O segredo foi guardado no `.env` local, ignorado pelo Git e com permissão `0600`; seu valor não integra este documento nem a evidência publicada. O cadastro da chave, isoladamente, não prova autenticação: a confirmação abaixo vem da resposta real da API.

## Primeiro acesso real, 09:54

Em **19/11/2026, 09:54:24–09:54:25 (America/Sao_Paulo)**, o [verificador](../scripts/verify_sptrans.py) realizou seis requisições HTTPS: autenticação, busca de linhas e duas sequências de busca de paradas/previsão. A API retornou `true` na autenticação. [JSON sanitizado da verificação](../evidencias/sptrans-verificacao-20261119T125425332800Z.json).

A busca por `8000` retornou **quatro registros de linha**. O script selecionou o primeiro serviço na ordenação e até dois sentidos distintos: `lt=8000`, `tl=1`, registrado como `8000-1`. Essa representação preserva o retorno observado; não deve ser substituída pelos códigos ou pelo serviço da demonstração sintética.

| Consulta | Linha/sentido descobertos | Paradas retornadas | Ponto selecionado | Resultado de previsão |
|---|---|---:|---|---|
| 1 | Código **2506**, sentido **1**, serviço **1** | 14 | **7014417 — ANGELICA B/C** | Consulta bem-sucedida, **retorno vazio** |
| 2 | Código **35274**, sentido **2**, serviço **1** | 13 | **614432 — BABY BARIONY C/B** | Consulta bem-sucedida, **uma previsão**, horário retornado **10:05** |

**Nesse primeiro acesso, somente uma das duas consultas retornou previsão.** Não houve previsão nos dois sentidos naquela amostra. O retorno vazio da primeira consulta não comprova falta de ônibus, suspensão da linha ou ausência de serviço.

A fonte informou `hr=09:54`; a data não vem nesse campo e foi inferida pelo dia mais próximo da consulta. A idade calculada desse relógio foi 25 segundos. Na única previsão recebida, a observação do veículo era de 09:54:15, com idade de dez segundos. Esses valores descrevem **aquela consulta histórica**, não uma chegada atual nem garantia de cumprimento. O JSON preserva horários e códigos públicos de linha/parada, sem coordenadas, identificadores de veículos, token, cookies ou corpo bruto da resposta.

A amostra foi limitada a uma parada por sentido, escolhida pelo menor código retornado, sem varredura ampla. Ela confirma acesso e existência de resposta nesse recorte e instante; não comprova cobertura de toda a linha ou do município.

## Promoção e jornada pública LIVE, 11:03–11:06

O [preflight posterior](../evidencias/cloud/azure-live-preflight-hardened.json), às 10:56:32–10:56:54, validou no container Azure a idade da fonte após a inferência: a consulta de chegada retornou vazio válido sem chamada à LLM; a busca de linhas retornou quatro registros reais, com chamada à LLM e fallback extrativo. Foram três checks aprovados, incluindo documental, sem previsão utilizável nessa amostra. O escopo era direto no Engine, ainda anterior à promoção pública.

A [implantação](../evidencias/cloud/azure-live-deployment.json) confirmou modo `live`, revisão `8b1e298a101eb9b90bf723efad268449381e2552` e digests. A [tentativa 1 do pipeline 44536511956](https://github.com/Salvittis/ponto-certo/actions/runs/44536511956/attempts/1) aprovou nove jobs e implantou os dois ambientes em DEMO. A [tentativa 2](https://github.com/Salvittis/ponto-certo/actions/runs/44536511956/attempts/2) reexecutou somente o deploy Azure para LIVE, com o mesmo commit e imagens já verificadas; AWS não foi reimplantada nessa promoção.

O [teste HTTPS público](../evidencias/cloud/azure-live-public.json), às **11:03:49–11:04:11**, aprovou seis checks. A consulta da linha **35274**, sentido **2**, ponto **614432**, retornou `not_found` com fonte/atualização; a consulta **2506**, sentido **1**, ponto **7014417**, retornou `ok`. A descoberta de linhas retornou quatro opções. Vazio é um resultado válido da consulta, sem concluir ausência de ônibus ou suspensão do serviço.

A [jornada pelo formulário público](../evidencias/jornada-publica-live.json), às **11:05–11:06**, confirmou o percurso completo: busca `8000` → **quatro registros** → seleção **2506/sentido 1** → **14 pontos** → **7014417 — ANGELICA B/C** → `ok`. A resposta exibiu **previsão 11:12, aproximadamente seis minutos no relógio da consulta**, fonte SPTrans Olho Vivo e atualização **11:06**. O aviso de simulação não estava presente. Esse horário é histórico; a previsão não garante chegada. As capturas registram [início](../evidencias/interface-publica-live-inicio.jpg), [linhas](../evidencias/interface-publica-live-linhas.jpg), [pontos](../evidencias/interface-publica-live-pontos.jpg), [formulário completo](../evidencias/interface-publica-live-completa.jpg) e [chegada](../evidencias/interface-publica-live-chegada.jpg).

As três rotas de identidade confirmaram a revisão às **11:06:52**. `/api/config` informou `live`; `/readyz` respondeu 200 com `sptrans_live_verified=false`. Esse campo segue o contrato de prontidão: configuração/modelo são verificados, sem autenticação ou consulta externa naquele endpoint. A comprovação do acesso real está nos testes HTTP e na jornada, não nesse sinal isolado. Os patches de produção posteriores ao estudo não são apresentados como código idêntico ao TEST24 nem como nova avaliação cega.

## Repetir com segurança

Depois de configurar `SPTRANS_TOKEN` no mecanismo de segredos do servidor ou no `.env` local protegido, sem inserir o valor na linha de comando:

```sh
.venv/bin/python -m scripts.verify_sptrans --query 8000
```

O script autentica de verdade, descobre os códigos a partir do retorno, limita a execução a seis requisições e salva uma nova evidência sanitizada com data/hora. A presença de um token, `DATA_MODE=live` ou uma resposta positiva de `/readyz` **não substitui esse teste de autenticação e consulta**. A prontidão da aplicação verifica configuração/modelo; não demonstra, por si, acesso real à SPTrans.

A integração no runtime, a promoção Azure LIVE e a jornada pública foram concluídas nas verificações acima. A manutenção do serviço e dos links durante a correção continua necessária; a submissão acadêmica cabe a Pedro/integrante. Uma nova execução deve gerar evidência própria, sem sobrescrever esses checkpoints ou o estudo original. AWS permanece DEMO, com avisos de simulação.

## Condições oficiais consultadas

As [Condições de Acesso do cadastro de desenvolvedor](https://www.sptrans.com.br/desenvolvedores/cadastro-desenvolvedores/registro-desenvolvedores-pf/) informam cadastro e dados gratuitos; proíbem alugar, sublicenciar ou vender os dados e não garantem completude, ausência de erros ou disponibilidade contínua. Não foi identificada licença padronizada como Creative Commons. Estas condições complementam a pesquisa anterior, sem alterar retroativamente os arquivos congelados da avaliação.

O [guia oficial](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/) descreve confirmação de cadastro por e-mail e criação do aplicativo em “Meus Aplicativos”. A [referência da API](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/) documenta autenticação e consultas, exige HTTPS e alerta para a cobertura limitada da categoria de paradas.
