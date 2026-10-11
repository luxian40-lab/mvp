import ast, subprocess, sys, pathlib

BASE = sys.argv[1]  # sha previo al split, p. ej. 56929af7
orig = subprocess.check_output(["git", "show", f"{BASE}:core/views.py"]).decode("utf-8")

def funcs(src):
    out = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for m in ast.walk(n):
                if isinstance(m, ast.ImportFrom):
                    m.level = 0  # ignora el cambio from . -> from ..
            out[n.name] = ast.dump(n)
    return out

a = funcs(orig)
b = {}
for p in pathlib.Path("core/views").glob("*.py"):
    if p.name == "__init__.py":
        continue
    for k, v in funcs(p.read_text(encoding="utf-8")).items():
        if k in b:
            print("DUPLICADA:", k, p)
        b[k] = v

print("faltan:   ", sorted(set(a) - set(b)))
print("nuevas:   ", sorted(set(b) - set(a)))
print("distintas:", sorted(k for k in a if k in b and a[k] != b[k]))
