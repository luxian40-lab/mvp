"""Uso local: reemplaza imports core.<stub> → core.conversacion.<stub> en *.py."""
import re
import sys
from pathlib import Path

STUB = sys.argv[1]
ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    (rf"\bfrom core\.{re.escape(STUB)}\b", f"from core.conversacion.{STUB}"),
    (rf"\bimport core\.{re.escape(STUB)}\b", f"import core.conversacion.{STUB}"),
    (rf"patch\('core\.{re.escape(STUB)}\.", f"patch('core.conversacion.{STUB}."),
    (rf'patch\("core\.{re.escape(STUB)}\.', f'patch("core.conversacion.{STUB}.'),
]


def main() -> None:
    changed = []
    for path in ROOT.rglob("*.py"):
        if path.match(f"core/{STUB}.py"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        new = text
        for pattern, repl in PATTERNS:
            new = re.sub(pattern, repl, new)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path)
    print(f"{STUB}: {len(changed)} archivos")
    for p in changed:
        print(f"  {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()