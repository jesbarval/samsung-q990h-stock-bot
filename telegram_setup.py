"""Obtiene tu chat_id de Telegram sin almacenar el token en disco.

Ejecuta `python telegram_setup.py` después de escribir /start a tu bot.
"""
import getpass
import requests


def main():
    token = getpass.getpass("Token creado con @BotFather (oculto al escribir): ").strip()
    if not token:
        print("Falta el token.")
        return
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=15
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            print("Telegram rechazó la solicitud. Revisa el token.")
            return
        chats = {
            (item.get("message") or item.get("edited_message") or {}).get("chat", {}).get("id")
            for item in data.get("result", [])
        }
        chats.discard(None)
        if not chats:
            print("No aparece ningún chat. Abre tu bot, pulsa Iniciar y envíale /start o 'hola'.")
        else:
            print("Chat ID encontrados (usa el de tu conversación):")
            for chat in sorted(chats):
                print(chat)
    except requests.RequestException:
        print("No se pudo consultar Telegram. Revisa la conexión y el token.")


if __name__ == "__main__":
    main()
