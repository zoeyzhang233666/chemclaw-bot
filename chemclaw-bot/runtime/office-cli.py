"""Optional conversion/recalculation adapter using an installed LibreOffice.

No files from the DSH installation are read. Source documents remain unchanged.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['convert', 'recalculate', 'render'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    parser.add_argument('--output-dir')
    parser.add_argument('--dpi', type=int, default=110)
    args = parser.parse_args()
    source = Path(args.input).resolve(strict=True)
    if args.action == 'render':
        try:
            import pypdfium2 as pdfium
        except ImportError as error:
            raise RuntimeError('Install pypdfium2 in the managed environment to render PDF pages.') from error
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        document = pdfium.PdfDocument(str(source))
        try:
            for number in range(len(document)):
                page = document[number]
                try:
                    bitmap = page.render(scale=args.dpi / 72)
                    try:
                        bitmap.to_pil().save(output / f'page-{number + 1:03}.png')
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        finally:
            document.close()
        return
    destination = Path(args.output).resolve()
    if source == destination:
        raise ValueError('Choose a separate output file; the source is never overwritten.')
    candidates = [os.environ.get('CHEMCLAW_LIBREOFFICE'), shutil.which('soffice'), shutil.which('libreoffice')]
    for base in [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]:
        if base:
            candidates.append(str(Path(base) / 'LibreOffice/program/soffice.exe'))
    executable = next((path for path in candidates if path and Path(path).is_file()), None)
    if not executable:
        raise RuntimeError('Install LibreOffice or set CHEMCLAW_LIBREOFFICE. Recalculation/conversion was not performed.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chemclaw-office-') as directory:
        output = Path(directory) / 'output'
        output.mkdir()
        profile = (Path(directory) / 'profile').as_uri()
        subprocess.run([executable, f'-env:UserInstallation={profile}', '--headless', '--convert-to', destination.suffix.lstrip('.'), '--outdir', str(output), str(source)], check=True, timeout=180, capture_output=True)
        converted = output / (source.stem + destination.suffix)
        if not converted.is_file():
            raise RuntimeError('LibreOffice did not produce the requested output.')
        shutil.copy2(converted, destination)
    print(destination)


if __name__ == '__main__':
    main()
