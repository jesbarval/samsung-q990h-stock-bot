"""Vigila el stock oficial de Samsung HW-Q990H/XC y avisa por correo electrónico.

Uso:
  python monitor.py --check-only    # consultar sin notificar
  python monitor.py --send-test     # enviar un email de prueba
  python monitor.py                 # comprobar y enviar alerta si aparece stock

El estado persistente (state.json) solo cambia cuando se confirma una transición
entre 'disponible' y 'agotado'. GitHub Actions lo conserva entre ejecuciones.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Literal

import requests
from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

PRODUCT_URL = (
    "https://www.samsung.com/es/audio-devices/soundbar/"
    "q990h-q-series-soundbar-hw-q990h-11-1-4ch-subwoofer-rear-speaker-2026-black-hw-q990h-xc/"
)
STATE_PATH = Path(__file__).with_name("state.json")
Stock = Literal["available", "out_of_stock", "unknown"]

MODEL = re.compile(r"(?:HW[-\s/]?Q990H|Samsung\s+Q990H)", re.I)
OUT_OF_STOCK = re.compile(
    r"producto\s+no\s+disponible|no\s+est[aá]\s+disponible|"
    r"sin\s+stock|temporalmente\s+agotad[oa]",
    re.I,
)
CTA = re.compile(
    r"(?:comprar(?:\s+ahora)?|a[nñ]adir\s+al\s+carrito|"
    r"agregar\s+al\s+carrito|buy\s+now|add\s+to\s+cart)",
    re.I,
)


def detect_stock(page_text: str, enabled_buy_button: bool) -> Stock:
    """Devuelve 'available' solo si se identifica la Q990H y se puede comprar.

    No interpreta menciones a productos sugeridos al pie como botones de esta barra.
    Una web inaccesible o con estructura desconocida es 'unknown', no 'agotado'.
    """
    compact = " ".join(page_text.split())
    match = MODEL.search(compact)
    if not match:
        return "unknown"
    area = compact[match.start():]
    # El bloque de ficha precede a la sección 'Destacados' en Samsung España.
    end = re.search(r"\bDestacados\b", area, re.I)
    if end:
        area = area[: end.start()]
    if OUT_OF_STOCK.search(area):
        return "out_of_stock"
    if enabled_buy_button and CTA.search(area):
        return "available"
    return "unknown"


def inspect_samsung() -> tuple[Stock, str]:
    """Obtiene la página renderizada (el botón se actualiza por JavaScript)."""
    with sync_playwright() as p:
        # GitHub ubuntu-24.04 incluye Google Chrome; se evita descargar Chromium
        # en cada uno de los ~288 controles diarios.
        browser_name = os.getenv("PW_BROWSER", "chrome")
        browser = p.chromium.launch(headless=True, channel=browser_name)
        try:
            context = browser.new_context(
                locale="es-ES",
                timezone_id="Europe/Madrid",
                viewport={"width": 1360, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            response = page.goto(PRODUCT_URL, wait_until="domcontentloaded", timeout=45000)
            if response is None or response.status >= 400:
                return "unknown", f"HTTP {response.status if response else 'sin respuesta'}"
            try:
                page.wait_for_function(
                    "document.body && /Q990H/i.test(document.body.innerText)",
                    timeout=12000,
                )
            except PWTimeout:
                return "unknown", "No se mostró el modelo Q990H"
            # Esperar a que se pinte el componente de compra de Samsung.
            page.wait_for_timeout(2500)
            main = page.locator("main")
            visible = (main if main.count() else page.locator("body")).inner_text(timeout=12000)

            enabled_buy_button = False
            for button in page.get_by_role("button").all():
                try:
                    if not (button.is_visible() and button.is_enabled()):
                        continue
                    label = " ".join((button.inner_text(timeout=600) or "").split())
                    aria = " ".join((button.get_attribute("aria-label") or "").split())
                    if CTA.fullmatch(label) or CTA.fullmatch(aria):
                        enabled_buy_button = True
                        break
                except Exception:
                    continue

            status = detect_stock(visible, enabled_buy_button)
            return status, f"Indicador de compra: {enabled_buy_button}; página analizada"
        finally:
            browser.close()


def send_email(subject: str, message: str) -> None:
    """Envía un correo a la misma dirección que se utilizó para abrir Resend.

    No se necesita la contraseña de Hotmail. La API key nunca se imprime ni
    se incluye en la URL, y GitHub la inyecta mediante un secret.
    """
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    recipient = os.environ.get("EMAIL_TO", "").strip()
    if not api_key or not recipient:
        raise RuntimeError("Faltan RESEND_API_KEY o EMAIL_TO en los secretos de GitHub")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
        raise RuntimeError("EMAIL_TO debe ser un correo electrónico válido")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": "Alerta Samsung Q990H <onboarding@resend.dev>",
            "to": [recipient],
            "subject": subject,
            "text": message,
        },
        timeout=25,
    )
    if not response.ok:
        if response.status_code == 403:
            raise RuntimeError(
                "Resend HTTP 403: regístrate en Resend con el MISMO Hotmail "
                "que has puesto como EMAIL_TO, o verifica un dominio remitente"
            )
        if response.status_code == 401:
            raise RuntimeError("Resend HTTP 401: revisa RESEND_API_KEY")
        raise RuntimeError(f"Resend HTTP {response.status_code}: no se pudo enviar el correo")
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Resend devolvió una respuesta no válida") from exc
    if not data.get("id"):
        raise RuntimeError("Resend no confirmó la aceptación del correo")


def load_status() -> Stock:
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("last_status", "unknown")
        return value if value in ("available", "out_of_stock", "unknown") else "unknown"
    except (FileNotFoundError, ValueError, TypeError, OSError):
        return "unknown"


def save_status(status: Stock) -> None:
    STATE_PATH.write_text(
        json.dumps({"last_status": status}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def should_notify(previous: Stock, current: Stock) -> bool:
    return current == "available" and previous != "available"


def run() -> int:
    parser = argparse.ArgumentParser(description="Alerta Samsung HW-Q990H por Hotmail")
    parser.add_argument("--check-only", action="store_true", help="Comprueba sin notificar")
    parser.add_argument("--send-test", action="store_true", help="Envía correo de prueba")
    args = parser.parse_args()

    if args.send_test:
        send_email(
            "✅ Prueba del aviso Samsung HW-Q990H",
            "El aviso por email funciona. GitHub comprobará la Samsung HW-Q990H/XC "
            "cada 5 minutos (las ejecuciones pueden retrasarse).",
        )
        print("Correo de prueba aceptado por Resend (revisar Hotmail y Correo no deseado).")
        return 0

    status, detail = inspect_samsung()
    print(f"Samsung HW-Q990H/XC — {status}: {detail}")
    if args.check_only:
        return 0
    previous = load_status()
    if status == "unknown":
        print("Resultado incierto. No se cambia el estado y no se envía ninguna alerta.")
        return 0
    if should_notify(previous, status):
        send_email(
            "🔔 ¡Samsung HW-Q990H DISPONIBLE!",
            "¡La Samsung HW-Q990H/XC parece estar de nuevo disponible en Samsung España!\n\n"
            "Comprueba la compra aquí:\n" + PRODUCT_URL + "\n\n"
            "Aviso automático; verifica la disponibilidad real antes de comprar.",
        )
        print("Se ha aceptado el aviso de stock por email.")
    elif status == "available":
        print("La barra sigue disponible y el aviso ya se envió; no repetir.")
    else:
        print("Sin stock. Se volverá a revisar en la próxima ejecución.")
    if status != previous:
        save_status(status)
        print("Estado actualizado.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        # No imprimir excepciones de requests: podrían contener datos sensibles.
        if isinstance(exc, RuntimeError):
            print(f"ERROR: {exc}", file=sys.stderr)
        else:
            print(f"ERROR: {type(exc).__name__}: fallo al ejecutar el monitor", file=sys.stderr)
        sys.exit(1)
