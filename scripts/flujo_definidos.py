"""Análisis de "asignado con seguridad" sobre una función, para mover tramos sin cambiar comportamiento.

`lecturas(func, tramo, locales)` recorre la función en orden de ejecución con el
conjunto de locales asignados en todo camino. Devuelve:
- entradas: locales que el tramo lee sin haberlos asignado antes dentro del tramo;
- inseguras: de esas, las que no están asignadas con seguridad al empezar el tramo;
- salidas: locales que el tramo asigna y que el código posterior puede leer
  sin reasignarlos antes.
Un camino que termina en return/raise/break/continue no aporta a la unión.
"""
from __future__ import annotations

import ast

TODO = None  # camino terminado: neutro en la intersección
COMPRENSIONES = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


def _inter(*conjuntos):
    vivos = [c for c in conjuntos if c is not TODO]
    if not vivos:
        return TODO
    salida = set(vivos[0])
    for c in vivos[1:]:
        salida &= c
    return salida


class Flujo:
    def __init__(self, tramo: list):
        self.primera, self.ultima = tramo[0], tramo[-1]
        self.lecturas: list[tuple[int, str, bool, str]] = []  # (línea, nombre, asignado, zona)
        self.al_entrar: set[str] | None = None
        self.asignados_tramo: set[str] = set()
        self.zona = 'antes'

    # --- expresiones ---
    def leer(self, n, definidos, ligados=frozenset()):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if n.id not in ligados:
                self.lecturas.append((n.lineno, n.id, n.id in definidos, self.zona))
            return
        if isinstance(n, COMPRENSIONES):
            propios = set(ligados)
            for g in n.generators:
                self.leer(g.iter, definidos, propios)
                propios |= {x.id for x in ast.walk(g.target) if isinstance(x, ast.Name)}
                for c in g.ifs:
                    self.leer(c, definidos, propios)
            for h in ([n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]):
                self.leer(h, definidos, propios)
            return
        if isinstance(n, ast.Lambda):
            a = n.args
            for d in a.defaults + [d for d in a.kw_defaults if d is not None]:
                self.leer(d, definidos, ligados)
            params = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
            params |= {x.arg for x in (a.vararg, a.kwarg) if x}
            self.leer(n.body, definidos, set(ligados) | params)
            return
        if isinstance(n, ast.NamedExpr):
            self.leer(n.value, definidos, ligados)
            self.asignar(n.target, definidos)
            return
        for h in ast.iter_child_nodes(n):
            self.leer(h, definidos, ligados)

    def asignar(self, objetivo, definidos):
        for x in ast.walk(objetivo):
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                definidos.add(x.id)
                if self.zona == 'tramo':
                    self.asignados_tramo.add(x.id)
            elif isinstance(x, (ast.Subscript, ast.Attribute)):
                self.leer(x.value, definidos)
                if isinstance(x, ast.Subscript):
                    self.leer(x.slice, definidos)

    def _marcar(self, nombre, definidos):
        definidos.add(nombre)
        if self.zona == 'tramo':
            self.asignados_tramo.add(nombre)

    # --- sentencias ---
    def bloque(self, stmts, definidos):
        actual = set(definidos)
        for s in stmts:
            if actual is TODO:
                break
            actual = self.sentencia(s, actual)
        return actual

    def sentencia(self, s, d):
        if s is self.primera:
            self.zona = 'tramo'
            self.al_entrar = set(d)
            d = set()
        resultado = self._sentencia(s, d)
        if s is self.ultima:
            self.zona = 'despues'
            base = self.al_entrar if resultado is not TODO else TODO
            if base is not TODO:
                resultado = (base | resultado) - self.asignados_tramo
        return resultado

    def _sentencia(self, s, d):
        d = set(d)
        if isinstance(s, ast.Expr):
            self.leer(s.value, d)
            return d
        if isinstance(s, ast.Assign):
            self.leer(s.value, d)
            for t in s.targets:
                self.asignar(t, d)
            return d
        if isinstance(s, ast.AnnAssign):
            if s.value is not None:
                self.leer(s.value, d)
                self.asignar(s.target, d)
            return d
        if isinstance(s, ast.AugAssign):
            self.leer(s.value, d)
            if isinstance(s.target, ast.Name):
                self.lecturas.append((s.lineno, s.target.id, s.target.id in d, self.zona))
            self.asignar(s.target, d)
            return d
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            for a in s.names:
                self._marcar((a.asname or a.name).split('.')[0], d)
            return d
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in s.decorator_list:
                self.leer(dec, d)
            self._marcar(s.name, d)
            return d
        if isinstance(s, ast.Return):
            if s.value is not None:
                self.leer(s.value, d)
            return TODO
        if isinstance(s, ast.Raise):
            for h in (s.exc, s.cause):
                if h is not None:
                    self.leer(h, d)
            return TODO
        if isinstance(s, (ast.Break, ast.Continue)):
            return TODO
        if isinstance(s, (ast.Pass, ast.Global, ast.Nonlocal)):
            return d
        if isinstance(s, ast.Delete):
            for t in s.targets:
                self.leer(t, d) if not isinstance(t, ast.Name) else d.discard(t.id)
            return d
        if isinstance(s, ast.Assert):
            self.leer(s.test, d)
            if s.msg is not None:
                self.leer(s.msg, d)
            return d
        if isinstance(s, ast.If):
            self.leer(s.test, d)
            return _inter(self.bloque(s.body, d), self.bloque(s.orelse, d))
        if isinstance(s, (ast.For, ast.AsyncFor)):
            self.leer(s.iter, d)
            dentro = set(d)
            self.asignar(s.target, dentro)
            self.bloque(s.body, dentro)
            fuera = self.bloque(s.orelse, d)
            return d if fuera is TODO else fuera
        if isinstance(s, ast.While):
            self.leer(s.test, d)
            self.bloque(s.body, d)
            fuera = self.bloque(s.orelse, d)
            return d if fuera is TODO else fuera
        if isinstance(s, (ast.With, ast.AsyncWith)):
            for item in s.items:
                self.leer(item.context_expr, d)
                if item.optional_vars is not None:
                    self.asignar(item.optional_vars, d)
            return self.bloque(s.body, d)
        if isinstance(s, ast.Try):
            tras_cuerpo = self.bloque(s.body, d)
            normal = self.bloque(s.orelse, tras_cuerpo) if (s.orelse and tras_cuerpo is not TODO) else tras_cuerpo
            ramas = [normal]
            for h in s.handlers:
                hd = set(d)
                if h.type is not None:
                    self.leer(h.type, hd)
                if h.name:
                    self._marcar(h.name, hd)
                fin_h = self.bloque(h.body, hd)
                if fin_h is not TODO and h.name:
                    fin_h.discard(h.name)
                ramas.append(fin_h)
            salida = _inter(*ramas)
            if s.finalbody:
                base = d if salida is TODO else salida
                fin = self.bloque(s.finalbody, base)
                return TODO if (fin is TODO or salida is TODO) else fin
            return salida
        if isinstance(s, ast.Match):
            raise SystemExit('match no soportado')
        for h in ast.iter_child_nodes(s):
            self.leer(h, d)
        return d


def lecturas(func: ast.FunctionDef, tramo: list, locales: set[str]) -> dict:
    f = Flujo(tramo)
    params = {x.arg for x in func.args.args + func.args.kwonlyargs}
    f.bloque(func.body, params)
    if f.al_entrar is None:
        raise SystemExit('El análisis no encontró el tramo')
    entradas = sorted({nom for _, nom, ok, z in f.lecturas if z == 'tramo' and not ok and nom in locales})
    inseguras = sorted(n for n in entradas if n not in f.al_entrar)
    salidas = sorted({nom for _, nom, ok, z in f.lecturas if z == 'despues' and not ok and nom in f.asignados_tramo})
    return {'entradas': entradas, 'inseguras': inseguras, 'salidas': salidas, 'asignados': f.asignados_tramo}
