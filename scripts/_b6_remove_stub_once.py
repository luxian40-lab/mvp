"""Uso: python scripts/_b6_remove_stub_once.py <stub> [extra_replacements...]"""
import pathlib
import re
import subprocess
import sys

STUB = sys.argv[1]
PAT = re.compile(r"core\." + re.escape(STUB) + r"(?!\w)")
REP = "core.analitica." + STUB

r = subprocess.run(
    ["git", "grep", "-l", f"core.{STUB}", "--", "*.py"],
    capture_output=True,
    text=True,
    cwd=pathlib.Path(__file__).resolve().parents[1],
)
files = [
    f
    for f in r.stdout.strip().splitlines()
    if f
    and f not in (f"core/{STUB}.py", f"core/analitica/{STUB}.py")
]
root = pathlib.Path(__file__).resolve().parents[1]
for rel in files:
    p = root / rel.replace("/", "\\") if "\\" not in rel else root / rel
    p = root / rel
    t = p.read_text(encoding="utf-8")
    nt = PAT.sub(REP, t)
    for extra in sys.argv[2:]:
        if "=" in extra:
            old, new = extra.split("=", 1)
            nt = nt.replace(old, new)
    if nt != t:
        p.write_text(nt, encoding="utf-8")
        print(rel)

stub_path = root / "core" / f"{STUB}.py"
if stub_path.is_file():
    stub_path.unlink()
    print(f"deleted core/{STUB}.py")