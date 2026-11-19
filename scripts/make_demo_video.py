#!/usr/bin/env python3
"""Compose a silent video from real, unmodified screenshots captured by the operator.

No screenshot is fabricated or edited. ffmpeg scales/pads each source inside a
video frame and renders explanatory text in separate bands. Four frames, 8s each.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SCENES = [
    {
        'name': 'inicio',
        'title': 'Ponto Certo | Informação para seguir viagem',
        'caption': 'Interface web, API e Qwen2.5-1.5B-Instruct local.\nMontagem de capturas reais; não é uma gravação contínua.',
    },
    {
        'name': 'documental',
        'title': 'Resposta documental com fonte',
        'caption': 'O RAG recupera trechos de uma base versionada com 18 trechos.\nA aplicação gera a resposta localmente e valida as fontes.',
    },
    {
        'name': 'chegada',
        'title': 'Chegada simulada, identificada na resposta',
        'caption': 'Fixture sintética: 19/11/2026, 10h em São Paulo; previsão às 10h08.\nNão é consulta ao vivo e não mede redução real da espera.',
    },
    {
        'name': 'esclarecimento',
        'title': 'Uma informação a mais para responder',
        'caption': 'A pergunta incompleta recebe um pedido de esclarecimento.\nAcesso real à SPTrans e validação pública são etapas separadas.',
    },
]


def ffmpeg_path(override=None):
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError('Executável ffmpeg informado não existe.')
        return str(path)
    installed = shutil.which('ffmpeg')
    if installed:
        return installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise RuntimeError('Instale ffmpeg ou imageio-ffmpeg==0.6.0 para gerar o vídeo.') from None


def font_path(override=None):
    candidates = [override] if override else [
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise RuntimeError('Fonte não encontrada; informe --font com um arquivo TTF.')


def filter_path(path):
    # ffmpeg's filter parser has escaping rules independent from the shell.
    return str(path).replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path, default=ROOT / 'evidencias')
    parser.add_argument('--output', type=Path, default=ROOT / 'evidencias/ponto-certo-demonstracao.mp4')
    parser.add_argument('--seconds', type=int, default=8)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--font')
    args = parser.parse_args()
    if not 5 <= args.seconds <= 15:
        parser.error('--seconds deve estar entre 5 e 15')
    binary = ffmpeg_path(args.ffmpeg)
    font = font_path(args.font)
    # Prefer viewport captures so text remains readable in the 1600x1200 output.
    sources = []
    for scene in SCENES:
        candidates = [args.screenshots / f"interface-{scene['name']}-viewport.jpg", args.screenshots / f"interface-{scene['name']}.jpg"]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            raise RuntimeError(f"Falta captura real da cena {scene['name']}; nenhum quadro será inventado.")
        sources.append(source.resolve())
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    version = subprocess.run([binary, '-version'], check=True, text=True, capture_output=True).stdout.splitlines()[0]
    records = []
    with tempfile.TemporaryDirectory(prefix='ponto-certo-video-') as tmp_dir:
        tmp = Path(tmp_dir)
        segments = []
        for index, (scene, source) in enumerate(zip(SCENES, sources)):
            title_file = tmp / f'{index}-title.txt'
            caption_file = tmp / f'{index}-caption.txt'
            title_file.write_text(scene['title'], encoding='utf-8')
            caption_file.write_text(scene['caption'], encoding='utf-8')
            segment = tmp / f'{index}.mp4'
            # Original screenshots remain untouched. Separate 90px/150px bands
            # leave 960px for the screenshot, preserving its whole composition.
            vf = (
                'scale=1520:960:force_original_aspect_ratio=decrease,'
                'pad=1600:1200:(ow-iw)/2:90+(960-ih)/2:color=0x102d42,'
                f"drawtext=fontfile='{filter_path(font)}':textfile='{filter_path(title_file)}':"
                'fontcolor=white:fontsize=32:x=40:y=29,'
                f"drawtext=fontfile='{filter_path(font)}':textfile='{filter_path(caption_file)}':"
                'fontcolor=white:fontsize=27:line_spacing=13:x=40:y=1081,'
                f"drawtext=fontfile='{filter_path(font)}':text='{index+1}/4 | Capturas reais - demonstracao local':"
                'fontcolor=0xaac5d1:fontsize=18:x=40:y=1170,'
                'setsar=1,format=yuv420p'
            )
            command = [binary, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-framerate', '24', '-i', str(source),
                       '-t', str(args.seconds), '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(segment)]
            subprocess.run(command, check=True)
            segments.append(segment)
            records.append({
                'scene': scene['name'], 'source': str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else source.name,
                'source_sha256': sha256(source),
                'source_mtime_utc': datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
                'starts_at_seconds': index * args.seconds, 'duration_seconds': args.seconds,
                'title': scene['title'], 'caption': scene['caption'],
            })
        concat = tmp / 'scenes.txt'
        concat.write_text(''.join("file '" + str(path).replace("'", "'\\''") + "'\n" for path in segments))
        subprocess.run([binary, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat),
                        '-c', 'copy', '-movflags', '+faststart', str(args.output)], check=True)
    size = args.output.stat().st_size
    if size >= 20_000_000:
        raise RuntimeError('Vídeo excedeu 20 MB; ajuste codificação antes de publicar.')
    manifest = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'format': 'Montagem em quadros de capturas reais; não é gravação contínua de tela.',
        'inference': 'Qwen2.5-1.5B-Instruct local, conforme contrato e smoke local; sem API comercial de LLM.',
        'transit_data': 'Fixture sintética; referência 2026-11-19T10:00:00-03:00. Não é captura ao vivo.',
        'ffmpeg': version, 'dimensions': [1600, 1200], 'fps': 24, 'duration_seconds': len(SCENES) * args.seconds,
        'audio': False, 'scenes': records, 'video_sha256': sha256(args.output), 'video_bytes': size,
    }
    manifest_path = args.output.with_suffix('.json')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'video': str(args.output), 'bytes': size, 'seconds': manifest['duration_seconds'], 'manifest': str(manifest_path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
