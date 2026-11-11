"""Extract the bundled public benchmark and saved outputs; no network requests."""
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parent
for name in ('benchmark.zip', 'results.zip'):
    with ZipFile(root / name) as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Archive path escapes repository')
        archive.extractall(root)
    print(f'Extracted {name}')
