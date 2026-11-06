"""Vigila el stock oficial de Samsung HW-Q990H/XC y avisa por Telegram.

Uso:
  python monitor.py --check-only    # consultar sin notificar
  python monitor.py --send-test     # enviar un Telegram de prueba
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


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en Secrets")
    # En POST body, no en query string, para evitar exponer el mensaje en la URL.
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        },
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"Telegram respondió HTTP {response.status_code}")
    try:
        if not response.json().get("ok", False):
            raise RuntimeError("Telegram no aceptó el mensaje")
    except ValueError as error:
        raise RuntimeError("Telegram no devolvió JSON válido") from error


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
    parser = argparse.ArgumentParser(description="Alerta Samsung HW-Q990H por Telegram")
    parser.add_argument("--check-only", action="store_true", help="No envía ni modifica estado")
    parser.add_argument("--send-test", action="store_true", help="Envía un mensaje de prueba")
    args = parser.parse_args()

    if args.send_test:
        send_telegram("✅ Bot Samsung HW-Q990H conectado. Recibirás avisos cuando haya stock.")
        print("Mensaje de prueba enviado.")
        return 0

    status, detail = inspect_samsung()
    print(f"Samsung HW-Q990H/XC — {status}: {detail}")
    if args.check_only:
        return 0

    previous = load_status()
    if status == "unknown":
        print("No hay evidencia suficiente. No cambiar estado ni enviar avisos.")
        return 0

    if should_notify(previous, status):
        print("¡Stock detectado! Intentando enviar alerta por Telegram…")
        send_telegram(
            "🔔 ¡La Samsung HW-Q990H/XC vuelve a tener stock en Samsung España!\n"
            "Compruébalo cuanto antes aquí:\n"
            + PRODUCT_URL
        )
        print("Alerta aceptada por Telegram.")
    elif status == "available":
        print("Sigue disponible; aviso ya enviado. No repetir.")
    else:
        print("Sin stock. Volver a revisar en la siguiente ejecución.")

    if status != previous:
        # Solo persistir cuando cambia: evita ~288 commits por día y mantiene el
        # estado previo si la notificación falla (para reintentar después).
        save_status(status)
        print("Estado actualizado.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        # No imprimir excepciones de requests, ya que pueden incluir la URL/token.
        print(f"ERROR: {type(exc).__name__}: no se completó la operación.", file=sys.stderr)
        sys.exit(1)
