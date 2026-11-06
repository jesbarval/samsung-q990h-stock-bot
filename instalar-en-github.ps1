# Instalador interactivo del monitor de stock Samsung HW-Q990H.
# No guarda el token de Telegram en archivos ni lo sube como codigo.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

# En Windows PowerShell 5.1, los errores de gh escritos en stderr pueden
# disparar ErrorActionPreference=Stop incluso cuando un fallo es ESPERABLE:
# no haber iniciado sesión o que el repositorio aún no exista.
function Test-Gh {
    param([string[]]$Argumentos)
    $preferenciaAnterior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & gh @Argumentos 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $preferenciaAnterior
    }
}

function Verificar-Herramienta {
    param([string]$Comando, [string]$WingetId, [string]$RutaAlternativa)
    if (Get-Command $Comando -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Necesitas instalar $Comando. Instala Git (https://git-scm.com/) y GitHub CLI (https://cli.github.com/) y vuelve a ejecutar este archivo."
    }
    Write-Host "Instalando $Comando con winget ..." -ForegroundColor Cyan
    & winget install --id $WingetId --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar $Comando. Instálalo desde su web oficial y repite el proceso." }
    if (Test-Path -LiteralPath $RutaAlternativa) {
        $env:Path = (Split-Path -Parent $RutaAlternativa) + ';' + $env:Path
    }
    if (-not (Get-Command $Comando -ErrorAction SilentlyContinue)) {
        throw "Se ha instalado $Comando, pero Windows aún no lo reconoce. Cierra esta ventana y vuelve a ejecutar INSTALAR-EN-GITHUB.cmd."
    }
}

try {
    Write-Host "=== Alerta Samsung HW-Q990H por Telegram: instalación GitHub ===" -ForegroundColor Cyan
    Write-Host "Se creará un repositorio PÚBLICO solo con código, SIN claves."
    Write-Host "GitHub revisará stock aproximadamente cada 5 minutos, sujeto a retrasos del servicio."
    $seguir = (Read-Host '¿Continuar? (S/N)').Trim().ToUpperInvariant()
    if ($seguir -notin @('S','SI','SÍ')) { Write-Host 'Cancelado.'; exit 0 }

    Verificar-Herramienta 'git' 'Git.Git' "$env:ProgramFiles\Git\cmd\git.exe"
    Verificar-Herramienta 'gh' 'GitHub.cli' "$env:ProgramFiles\GitHub CLI\gh.exe"

    if (-not (Test-Gh -Argumentos @('auth', 'status', '--hostname', 'github.com'))) {
        Write-Host 'Ahora GitHub te pedirá iniciar sesión en el navegador.' -ForegroundColor Cyan
        & gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar sesión en GitHub.' }
    }
    $usuario = ((& gh api user --jq '.login') | Out-String).Trim()
    if (-not $usuario) { throw 'No se pudo leer tu usuario de GitHub.' }

    $nombre = (Read-Host 'Nombre del repositorio [alerta-q990h-telegram]').Trim()
    if (-not $nombre) { $nombre = 'alerta-q990h-telegram' }
    if ($nombre -notmatch '^[A-Za-z0-9._-]+$') { throw 'El nombre del repositorio contiene caracteres no admitidos.' }
    $repo = "$usuario/$nombre"

    $remoto = ''
    if (Test-Path '.git') {
        $remoto = ((& git remote get-url origin 2>$null) | Out-String).Trim()
    }
    if ($remoto) {
        $repoExistente = ((& gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>$null) | Out-String).Trim()
        if (-not $repoExistente) { throw 'Hay un repositorio Git local, pero no se pudo identificar el remoto.' }
        $repo = $repoExistente
        Write-Host "Se actualizarán los secretos del repositorio existente: $repo" -ForegroundColor Yellow
    } else {
        # Un repositorio inexistente es normal: lo crearemos a continuación.
        if (Test-Gh -Argumentos @('repo', 'view', $repo, '--json', 'name')) {
            throw "El repositorio https://github.com/$repo ya existe. Si es tuyo, usa otro nombre o actualízalo manualmente."
        }
        if (-not (Test-Path '.git')) {
            & git init -b main
            if ($LASTEXITCODE -ne 0) { throw 'git init ha fallado.' }
        }
        & git config user.name $usuario
        & git config user.email "$usuario@users.noreply.github.com"
        & git add .
        & git commit -m 'Crear monitor Samsung Q990H con alerta Telegram'
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el commit inicial.' }
        Write-Host 'Creando y subiendo el repositorio público...' -ForegroundColor Cyan
        & gh repo create $repo --public --source . --remote origin --push --description 'Aviso por Telegram cuando Samsung HW-Q990H/XC vuelve a tener stock'
        if ($LASTEXITCODE -ne 0) { throw 'GitHub no pudo crear o subir el repositorio.' }
    }

    Write-Host "Abre https://t.me/BotFather en Telegram, crea el bot con /newbot y envíale /start." -ForegroundColor Cyan
    $tokenSeguro = Read-Host 'Pega aquí el TOKEN de BotFather (queda oculto)' -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSeguro)
    try {
        $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        if (-not $token -or $token -notmatch '^\d+:[A-Za-z0-9_-]+$') { throw 'El token de Telegram no tiene el formato esperado.' }
        $id = ''
        try {
            $resultado = Invoke-RestMethod -Uri "https://api.telegram.org/bot${token}/getUpdates" -Method Get -TimeoutSec 20
            $chats = @($resultado.result | ForEach-Object {
                if ($_.message -and $_.message.chat) { $_.message.chat.id }
                elseif ($_.edited_message -and $_.edited_message.chat) { $_.edited_message.chat.id }
            } | Where-Object { $null -ne $_ } | Sort-Object -Unique)
            if ($chats.Count -eq 1) {
                $id = [string]$chats[0]
                Write-Host "Chat ID encontrado automáticamente: $id" -ForegroundColor Green
            } elseif ($chats.Count -gt 1) {
                Write-Host "Chats encontrados: $($chats -join ', ')" -ForegroundColor Yellow
            } else {
                Write-Host 'No se ve tu chat. En Telegram abre tu bot y envíale /start o hola.' -ForegroundColor Yellow
            }
        } catch {
            Write-Host 'No se pudo recuperar el Chat ID automáticamente. Comprueba el token y /start.' -ForegroundColor Yellow
        }
        if (-not $id) { $id = (Read-Host 'Introduce el Chat ID (número de Telegram)').Trim() }
        if ($id -notmatch '^-?\d+$') { throw 'El Chat ID debe ser numérico.' }

        # Se transmiten los secretos por stdin; no se incluyen en commits o archivos.
        $token | & gh secret set TELEGRAM_BOT_TOKEN --repo $repo --app actions
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo guardar TELEGRAM_BOT_TOKEN como secreto de GitHub.' }
        $id | & gh secret set TELEGRAM_CHAT_ID --repo $repo --app actions
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo guardar TELEGRAM_CHAT_ID como secreto de GitHub.' }
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        Remove-Variable token -ErrorAction SilentlyContinue
        Remove-Variable tokenSeguro -ErrorAction SilentlyContinue
    }

    # Permite que el workflow actualice state.json cuando detecta cambios.
    & gh api -X PUT "repos/$repo/actions/permissions/workflow" -f default_workflow_permissions=write -F can_approve_pull_request_reviews=false 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Aviso: activa Read and write permissions en Settings > Actions > General.' -ForegroundColor Yellow
    }
    Write-Host 'Enviando una ejecución de prueba a GitHub Actions...' -ForegroundColor Cyan
    & gh workflow run vigilar-stock.yml --repo $repo -f prueba_telegram=true
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Si el workflow aún no se ve, espera a que GitHub lo indexe y ejecútalo desde Actions > Run workflow.' -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host 'Repositorio configurado:' -ForegroundColor Green
    Write-Host "https://github.com/$repo"
    Write-Host 'Comprueba la primera ejecución y el mensaje de Telegram en:'
    Write-Host "https://github.com/$repo/actions"
    Write-Host 'Las comprobaciones programadas empiezan cuando GitHub habilita el workflow.'
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
