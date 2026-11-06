# Bot Telegram · Stock Samsung HW-Q990H/XC (cada 5 minutos)

Este bot revisa la **tienda oficial de Samsung España** y te envía un mensaje de Telegram cuando la barra de sonido **HW-Q990H/XC** pasa a estar disponible.

**Página vigilada:** https://www.samsung.com/es/audio-devices/soundbar/q990h-q-series-soundbar-hw-q990h-11-1-4ch-subwoofer-rear-speaker-2026-black-hw-q990h-xc/

**Funcionamiento:** GitHub Actions intenta ejecutar el bot cada 5 minutos, también con el PC apagado. No hay garantía de puntualidad exacta: GitHub puede retrasar u omitir ejecuciones. El bot solo manda un aviso al detectar disponibilidad; no vuelve a mandar alertas hasta que primero haya observado agotamiento y luego una nueva reposición.

## Instalación rápida para Windows (recomendada)

**Versión corregida:** evita el error `GraphQL: Could not resolve to a Repository` al comprobar un repositorio que aún no existe y gestiona correctamente la ausencia inicial de sesión en PowerShell. Si viste ese error, extrae de nuevo el ZIP corregido en una carpeta nueva (no reutilices un `.git` de una instalación incompleta).


1. Descomprime el ZIP en una carpeta y abre **`INSTALAR-EN-GITHUB.cmd`** con doble clic.
2. Confirma que quieres crear un repositorio **público** (el código es visible, pero no tus claves). El instalador comprueba Git y GitHub CLI; si faltan, intenta instalarlos con `winget`.
3. Inicia sesión en GitHub mediante el navegador cuando se te solicite.
4. Crea el bot en [@BotFather](https://t.me/BotFather) usando `/newbot` y envíale `/start`. Introduce el **token** directamente en la ventana del instalador (no me lo envíes).
5. El programa intentará encontrar tu **Chat ID**, guardará ambos datos como secretos cifrados de GitHub y lanzará un mensaje de prueba a Telegram. Comprueba que llega y revisa el enlace a **Actions** mostrado.

Este instalador solo puede completar los pasos tras iniciar sesión con tu cuenta de GitHub y proporcionar los datos del bot en tu propio ordenador. No lo hemos ejecutado con credenciales reales ni verificado el envío en tu cuenta.

## 1. Crear un bot gratis en Telegram

1. Abre [@BotFather](https://t.me/BotFather) en Telegram.
2. Envía `/newbot`, elige un nombre y después un usuario terminado en `bot`.
3. BotFather te mostrará una **clave o token** como `123456789:ABC...`. **No compartas el token, ni lo subas a GitHub**.
4. Abre tu bot, pulsa **Iniciar** y envía `/start` (también puedes escribir `hola`).

## 2. Averiguar tu Chat ID

La manera sencilla sin instalar nada es abrir en tu navegador, sustituyendo `TU_TOKEN` por la clave anterior:

`https://api.telegram.org/botTU_TOKEN/getUpdates`

Deberías ver una respuesta JSON que contiene algo parecido a `"chat":{"id":123456789,...}`. **Ese número es tu `TELEGRAM_CHAT_ID`.** Si `result` está vacío, envía un mensaje nuevo a tu bot y actualiza la página. No compartas ese enlace, ya que contiene tu token.

Alternativamente, en tu ordenador, con Python instalado:

```bash
pip install requests
python telegram_setup.py
```

Este ayudante solicitará el token de forma oculta y mostrará los Chat ID. No guardará el token en archivos.

## 3. Subir a GitHub (gratis en repositorios públicos)

1. Entra en https://github.com/new y crea un repositorio con cualquier nombre, por ejemplo `alerta-q990h-telegram`.
2. Elige **Public** si quieres aprovechar los minutos de GitHub Actions gratis. Los secretos que configures no se publican. **Importante:** no incluyas tu token ni tu ID en archivos del repositorio. GitHub da una cuota limitada de minutos en repositorios privados, que puede agotarse revisando cada 5 minutos.
3. Extrae este ZIP y sube **todos los archivos**, incluida la carpeta oculta `.github/workflows/`. Puedes hacerlo con `git` o con **Add file → Upload files**. Si Windows oculta `.github`, activa la visualización de elementos ocultos.
4. Ve a **Settings → Secrets and variables → Actions → New repository secret**. Crea exactamente estos dos secretos:

   | Nombre | Valor |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | Token de @BotFather |
   | `TELEGRAM_CHAT_ID` | Número de tu chat |

5. Ve a **Settings → Actions → General → Workflow permissions** y comprueba que esté seleccionado **Read and write permissions** (necesario para que el bot recuerde si ya te avisó). Guarda los cambios.
6. Abre **Actions → Alerta de stock Samsung Q990H por Telegram → Run workflow**. Marca **prueba_telegram** para recibir primero un mensaje de prueba. Vuelve a ejecutarlo sin marcar la casilla para probar la consulta de Samsung. Después, GitHub seguirá lanzando el control mediante `cron: '*/5 * * * *'`.

**Si al subir el ZIP GitHub no detecta el workflow**, asegúrate de que el archivo queda en `.github/workflows/vigilar-stock.yml` en la rama por defecto y que no has creado una carpeta extra al nivel superior.

## 4. Enviar un mensaje de prueba

En GitHub: ejecuta **Run workflow** y marca la opción **prueba_telegram**. También puedes probarlo desde tu ordenador con:

```bash
pip install -r requirements.txt
# Linux / macOS:
TELEGRAM_BOT_TOKEN='TU_TOKEN' TELEGRAM_CHAT_ID='TU_CHAT_ID' python monitor.py --send-test
# Windows PowerShell:
$env:TELEGRAM_BOT_TOKEN='TU_TOKEN'
$env:TELEGRAM_CHAT_ID='TU_CHAT_ID'
python monitor.py --send-test
```

Cuando el bot vea stock real, recibirás:

> 🔔 ¡La Samsung HW-Q990H/XC vuelve a tener stock en Samsung España!\nCompruébalo cuanto antes aquí:\nhttps://www.samsung.com/es/audio-devices/soundbar/q990h-q-series-soundbar-hw-q990h-11-1-4ch-subwoofer-rear-speaker-2026-black-hw-q990h-xc/

## 5. Qué hacer si no funciona

- En **Actions**, abre el último workflow y lee sus registros. `unknown` significa que Samsung no mostró información concluyente: no se enviará un falso aviso.
- Si Telegram no recibe nada, comprueba que has enviado `/start` al bot y que el `TELEGRAM_CHAT_ID` es correcto.
- Si GitHub no permite realizar un commit a `state.json`, activa **Read and write permissions**.
- Si la tienda utiliza protecciones antibot, cambia el HTML o el botón de compra, el detector puede devolver `unknown` y requerir ajuste. No está garantizado que Samsung permita siempre la consulta automatizada.
- Si GitHub retrasa o no ejecuta un cron, la siguiente ejecución podrá volver a comprobarlo. GitHub puede desactivar workflows programados de repositorios públicos tras 60 días de inactividad; vigila que siga activo.
- Para parar el seguimiento: **Actions → Alerta de stock Samsung Q990H por Telegram → Disable workflow**.

## Pruebas y opciones para desarrolladores

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --check-only
```

`monitor.py` usa Playwright con el **Chrome preinstalado en GitHub Ubuntu**. En un ordenador donde solo tengas Chromium instalado, establece `PW_BROWSER=chromium` y ejecuta `python -m playwright install chromium`. No se incluye ningún token personal en el código.

**Limitación:** este proyecto se ha preparado y probado unitariamente, pero no se ha desplegado en tu cuenta de GitHub ni se ha verificado el acceso real a Samsung desde un runner de GitHub. Las comprobaciones periódicas solo empezarán después de configurar tu repositorio y tu cuenta de Telegram.
