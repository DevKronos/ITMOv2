"""Единая проверка; OpenCode сможет вызывать её из своего hook."""
import ast
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for directory in ('app','tests','scripts'):
    for path in (root/directory).rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
print('Синтаксис Python: OK',flush=True)
raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q'],cwd=root))
