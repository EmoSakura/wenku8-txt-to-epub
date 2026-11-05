"""Build and smoke-test a native package; run on the target operating system."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import core
from main import VERSION


def run(args, **kwargs):
    subprocess.run([str(value) for value in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    release = ROOT / 'release'
    output = ROOT / 'test-output'
    release.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    name = 'WenkuTxtEpub'
    options = ['--noconfirm', '--clean', '--name', name, '--windowed', '--add-data', 'assets:assets']
    if sys.platform == 'win32':
        options += ['--onefile', '--icon', 'assets/app.ico']
    elif sys.platform == 'darwin':
        from PIL import Image
        icon = output / 'app.icns'
        Image.open(ROOT / 'assets/app-icon.png').resize((1024, 1024)).save(icon)
        options += ['--onedir', '--icon', str(icon), '--osx-bundle-identifier', 'com.emosakura.wenkutxtepub']
    else:
        options += ['--onedir']
    run([sys.executable, '-m', 'PyInstaller', *options, 'app/main.py'], timeout=900)
    if sys.platform == 'win32':
        binary = ROOT / 'dist' / (name + '.exe')
    elif sys.platform == 'darwin':
        binary = ROOT / 'dist' / (name + '.app') / 'Contents/MacOS' / name
    else:
        binary = ROOT / 'dist' / name / name
    sample = output / 'sample.txt'
    sample.write_text('<打包测试>\n第一卷 起点\n第一章 测试\n中文 & 繁體 < >，こんにちは。\n第二卷 尾声\n结束。', encoding='utf-8')
    cli_report = output / 'cli.json'
    run([binary, '--convert', sample, '--output', output / 'cli-export', '--report', cli_report], timeout=120)
    core.verify(json.loads(cli_report.read_text(encoding='utf-8'))['epub'])
    gui_report = output / 'gui.json'
    command = [binary, '--smoke-test', gui_report]
    if sys.platform.startswith('linux'):
        command = ['xvfb-run', '-a', *command]
    run(command, timeout=120)
    report = json.loads(gui_report.read_text(encoding='utf-8'))
    assert report['window_visible'] and report['cover_preview'] and report['txt_export'], report
    core.verify(report['selected_volume_export'])
    stem = f'{name}-{VERSION}-{args.platform}'
    if sys.platform == 'win32':
        artifact = release / (stem + '.exe')
        shutil.copy2(binary, artifact)
    elif sys.platform == 'darwin':
        artifact = release / (stem + '.zip')
        run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', ROOT / 'dist' / (name + '.app'), artifact])
    else:
        artifact = release / (stem + '.tar.gz')
        with tarfile.open(artifact, 'w:gz') as archive:
            archive.add(ROOT / 'dist' / name, arcname=name)
    report.update({'artifact': artifact.name, 'python': platform.python_version(), 'architecture': platform.architecture()[0], 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'checks': ['unittest', 'packaged CLI conversion', 'EPUB ZIP/XML/resources', 'packaged GUI launch', 'anime icon loading', 'selected volume export', 'cover preview', 'TXT export']})
    # Reports contain synthetic data only, and no machine-specific output paths.
    report.pop('selected_volume_export', None)
    (release / (args.platform + '-test-report.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
