"""Verify that the downloadable skill is portable and contains no local data."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'zhihu-archive'


def test_skill_metadata_is_utf8_and_discoverable():
    frontmatter = SKILL.joinpath('SKILL.md').read_text(encoding='utf-8').split('---', 2)[1]
    metadata = yaml.safe_load(frontmatter)
    assert metadata['name'] == SKILL.name
    assert 0 < len(metadata['description']) <= 1024
    interface = yaml.safe_load(SKILL.joinpath('agents/openai.yaml').read_text(encoding='utf-8'))['interface']
    assert '$zhihu-archive' in interface['default_prompt']
    assert 25 <= len(interface['short_description']) <= 64


def test_release_excludes_unlisted_files_and_runs_after_extraction(tmp_path):
    repo = tmp_path / 'repo'
    source = repo / 'skills' / SKILL.name
    shutil.copytree(SKILL, source, ignore=shutil.ignore_patterns('__pycache__'))
    (repo / 'scripts').mkdir()
    shutil.copy2(ROOT / 'scripts/package_skill.py', repo / 'scripts/package_skill.py')
    injected = ['.auth/session.json', 'scripts/session.txt', 'assets/user-note.md', 'cookies.json']
    for relative in injected:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('PRIVATE_TEST_SENTINEL', encoding='utf-8')
    result = subprocess.run([sys.executable, '-X', 'utf8', str(repo / 'scripts/package_skill.py')], capture_output=True)
    assert result.returncode == 0, result.stderr.decode('utf-8')
    with zipfile.ZipFile(repo / 'dist/zhihu-archive.zip') as archive:
        for relative in injected:
            assert f'zhihu-archive/{relative}' not in archive.namelist()
        assert all(b'PRIVATE_TEST_SENTINEL' not in archive.read(name) for name in archive.namelist())
        archive.extractall(tmp_path / 'installed')
    installed = tmp_path / 'installed' / 'zhihu-archive'
    help_result = subprocess.run([sys.executable, '-X', 'utf8', str(installed / 'scripts/zhihu_archive.py'), 'crawl', '--help'], capture_output=True)
    assert help_result.returncode == 0, help_result.stderr.decode('utf-8')
    assert b'--cookie-file' in help_result.stdout
    assert installed.joinpath('assets/reader.html').is_file()
    assert installed.joinpath('references/authentication.md').is_file()
