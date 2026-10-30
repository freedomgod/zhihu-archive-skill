"""Build an allowlisted skill ZIP; optionally install this single skill."""
import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'skills' / 'zhihu-archive'
release_files = (
    'SKILL.md', 'LICENSE.txt', 'agents/openai.yaml',
    'references/authentication.md', 'references/operation.md', 'references/setup.md',
    'scripts/zhihu_archive.py', 'scripts/archive.py', 'scripts/auth.py',
    'scripts/browser.py', 'scripts/client.py', 'scripts/requirements.txt',
    'assets/reader.html', 'assets/reader.css', 'assets/reader.js',
    'assets/chrome-cookie-export/manifest.json',
    'assets/chrome-cookie-export/popup.html', 'assets/chrome-cookie-export/popup.js',
)
files = [source / name for name in release_files]
for path in files:
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
        raise SystemExit(f'Missing or unsafe release file: {path.relative_to(source)}')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install', type=Path, help='Also copy into a new zhihu-archive skill folder')
args = parser.parse_args()
output = root / 'dist'
output.mkdir(exist_ok=True)
zip_path = output / 'zhihu-archive.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in files:
        entry = zipfile.ZipInfo('zhihu-archive/' + p.relative_to(source).as_posix())
        entry.create_system = 3
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        z.writestr(entry, p.read_text(encoding='utf-8').encode('utf-8'))
(output / 'SHA256SUMS').write_text(hashlib.sha256(zip_path.read_bytes()).hexdigest() + '  zhihu-archive.zip\n', encoding='utf-8')
print('packaged_files:', len(files))
if args.install:
    destination = args.install.resolve()
    if destination.name != 'zhihu-archive':
        raise SystemExit('Destination must be the zhihu-archive skill folder')
    if destination.exists():
        raise SystemExit('Destination already exists; inspect before updating')
    for p in files:
        target = destination / p.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    print('installed:', destination)
