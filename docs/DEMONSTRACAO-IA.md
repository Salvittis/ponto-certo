# Demonstração da IA — Ponto Certo

O vídeo desta entrega é uma **montagem silenciosa de quatro capturas reais da aplicação local**, com oito segundos por cena. Não é uma gravação contínua: os intervalos de digitação, espera e navegação não aparecem. As imagens foram obtidas no navegador pelo operador/agente, após executar as consultas. Nenhuma interface ou resposta é redesenhada pelo script.

## O que o vídeo demonstra

| Tempo | Cena | Evidência visual |
|---|---|---|
| 0–8 s | Entrada do assistente | Formulário, exemplos de pergunta e acesso à SPTrans. |
| 8–16 s | Pergunta documental | Resposta sobre previsão não ser garantia, com fonte. |
| 16–24 s | Chegada simulada | Linha 8000, código 1273, ponto 4200153; previsão sintética 10h08 e aviso explícito. |
| 24–32 s | Esclarecimento | Pedido de informação adicional diante de pergunta incompleta. |

A interface chama `POST /api/ask`. A API integra recuperação documental, consultas controladas, Qwen2.5-1.5B-Instruct Q4_K_M executado localmente no llama.cpp e validação determinística de saída. O corpus versionado contém 18 trechos. As respostas finais também podem ser restringidas ou substituídas pelas regras do agente; o vídeo não atribui toda a formulação ao modelo.

O teste da jornada com o modelo real está em [smoke-local.json](../evidencias/smoke-local.json). A comparação das três configurações e as saídas do modelo pertencem à avaliação, não a este vídeo.

## Dados e origem temporal

- As capturas são da aplicação local, obtidas em 19/11/2026. O manifesto gerado registra os arquivos-fonte, seus hashes SHA-256 e os horários de modificação em UTC; esses horários registram os arquivos, não são horários da SPTrans.
- A previsão exibida usa a [fixture sintética versionada](../dados/fixtures/sptrans-demo.json), com referência **19/11/2026 às 10h, America/Sao_Paulo**. A chegada às 10h08 representa oito minutos somente no relógio dessa simulação.
- A fixture foi escrita pelo projeto a partir do formato documentado pela SPTrans. Ela **não é uma captura da API externa** e não comprova linha, ponto, itinerário ou operação atuais.
- O vídeo não comprova acesso autenticado à SPTrans nem publicação em Cloud. A validação da URL pública deve ter evidência própria.
- Não há medição de redução efetiva da espera. O benefício proposto é facilitar o acesso à informação e reduzir a incerteza.

## Reproduzir a montagem

Requer Python 3.11+, FFmpeg com `libx264` e `drawtext`, e uma fonte TTF. O vídeo não exige rede, modelo ou API durante a montagem: usa as capturas já obtidas. A inferência real precisa ter ocorrido antes de capturar as cenas.

```bash
# Dependência opcional de autoria, separada da aplicação de produção:
.venv/bin/pip install imageio-ffmpeg==0.6.0
.venv/bin/python scripts/make_demo_video.py
```

Se `ffmpeg` já estiver no PATH, o pacote opcional não é necessário. É possível usar `--ffmpeg /caminho/ffmpeg` e `--font /caminho/fonte.ttf`.

O script procura `evidencias/interface-{inicio,documental,chegada,esclarecimento}-viewport.jpg` e, na ausência de cada viewport, usa `interface-{cena}.jpg`. Prefira capturas de viewport enquadrando o resultado para manter o texto legível. Ele interrompe se qualquer cena estiver ausente; nunca cria uma imagem substituta.

A montagem apenas redimensiona proporcionalmente e posiciona as capturas no vídeo. Títulos e legendas ficam em faixas separadas. Saída: H.264, 1600×1200, 24 fps, 32 segundos, sem áudio e menor que 20 MB. O manifesto JSON acompanha o MP4.

## Verificação executada

Vídeo gerado em 19/11/2026: 32,00 segundos, 1600×1200, 24 fps, H.264, sem áudio, **469.989 bytes**. O FFmpeg decodificou o arquivo completo sem erro. Foram extraídos e inspecionados visualmente os quadros de 4, 12, 20 e 28 segundos: interface, fontes, respostas e legendas estão legíveis, sem corte das capturas nem sobreposição de texto. A inspeção verifica a montagem, não substitui o teste da aplicação.

## Artefatos e link para entrega

- [Vídeo MP4](../evidencias/ponto-certo-demonstracao.mp4)
- [Manifesto e hashes](../evidencias/ponto-certo-demonstracao.json)
- [Script de reprodução](../scripts/make_demo_video.py)

O link público definitivo depende do push ao repositório público da equipe. A publicação do arquivo no GitHub deve ser conferida antes de usar o link na submissão. Não existe exigência de duração ou plataforma de vídeo nas páginas 28–31 do enunciado; a duração acima é uma escolha do projeto.
