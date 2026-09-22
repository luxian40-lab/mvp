"""Crea/envía plantilla Meta de prueba al celular smoke (no imprime el token)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DESTINO = "573026480629"
PHONE_ID = "495439026995771"
TPL_NAME = "eki_sandbox_prueba"
TPL_BODY = (
    "Hola, soy eki. Responde este mensaje para abrir el sandbox "
    "(agentes y cursos). Escribe hola."
)


def _token() -> str:
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("WHATSAPP_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("WHATSAPP_TOKEN missing in .env")


def _req(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        return exc.code, body


def _err(body: dict) -> str:
    err = body.get("error") or {}
    if isinstance(err, dict):
        return f"{err.get('code')} {err.get('message', body)}"
    return str(body)[:300]


def main() -> int:
    token = _token()
    print("destino", DESTINO)
    print("phone_id", PHONE_ID)

    st, debug = _req(
        "GET",
        f"https://graph.facebook.com/v21.0/debug_token?input_token={token}",
        token,
    )
    data = (debug.get("data") or {}) if st == 200 else {}
    waba = ""
    granular = data.get("granular_scopes") or []
    target_ids = []
    for g in granular:
        target_ids.extend(g.get("target_ids") or [])
    print("token_ok", st == 200, "app_id", data.get("app_id", ""), "type", data.get("type", ""))
    print("target_ids", ",".join(target_ids[:8]))

    # Phone metadata
    st, phone = _req(
        "GET",
        f"https://graph.facebook.com/v21.0/{PHONE_ID}?fields=id,display_phone_number,verified_name",
        token,
    )
    print("phone_meta", st, phone.get("display_phone_number"), phone.get("verified_name"))

    # Try common WABA discovery
    for candidate in target_ids:
        st, probe = _req(
            "GET",
            f"https://graph.facebook.com/v21.0/{candidate}/message_templates?limit=5",
            token,
        )
        if st == 200:
            waba = candidate
            names = [t.get("name") for t in (probe.get("data") or [])]
            print("WABA", waba, "templates", ",".join(n for n in names if n)[:200])
            break
        print("probe_not_waba", candidate, st, _err(probe)[:120])

    # 1) Send hello_world (preaprobada en muchas apps)
    hello = {
        "messaging_product": "whatsapp",
        "to": DESTINO,
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    }
    st, sent = _req(
        "POST",
        f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages",
        token,
        hello,
    )
    mid = ((sent.get("messages") or [{}])[0].get("id")) if st in (200, 201) else ""
    print("hello_world", st, "id", mid or _err(sent))

    if not waba:
        print("NO_WABA no se pudo crear plantilla propia; usa hello_world si salio 200")
        return 0 if mid else 1

    # 2) Create utility template if missing
    st, existing = _req(
        "GET",
        f"https://graph.facebook.com/v21.0/{waba}/message_templates?name={TPL_NAME}",
        token,
    )
    found = [t for t in (existing.get("data") or []) if t.get("name") == TPL_NAME]
    if found:
        print("template_exists", found[0].get("status"), found[0].get("id"))
        tpl_status = found[0].get("status")
    else:
        st, created = _req(
            "POST",
            f"https://graph.facebook.com/v21.0/{waba}/message_templates",
            token,
            {
                "name": TPL_NAME,
                "language": "es",
                "category": "UTILITY",
                "components": [{"type": "BODY", "text": TPL_BODY}],
            },
        )
        print("template_create", st, created.get("id"), created.get("status") or _err(created))
        tpl_status = created.get("status")
        if st == 200 and created.get("id"):
            print("WABA_ID", waba)

    if str(tpl_status or "").upper() in {"APPROVED", "ACTIVE"}:
        st, sent2 = _req(
            "POST",
            f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages",
            token,
            {
                "messaging_product": "whatsapp",
                "to": DESTINO,
                "type": "template",
                "template": {"name": TPL_NAME, "language": {"code": "es"}},
            },
        )
        mid2 = ((sent2.get("messages") or [{}])[0].get("id")) if st in (200, 201) else ""
        print("eki_sandbox_prueba", st, "id", mid2 or _err(sent2))
    else:
        print("template_pending_or_unusable", tpl_status)

    print("WABA_ID", waba)
    return 0


if __name__ == "__main__":
    sys.exit(main())
