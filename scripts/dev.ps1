<#
  Starts Nora MedLink for local work, each part in its own PowerShell window:
    1. the FastAPI backend (port 8000)
    2. the Next.js frontend (port 3000)
    3. the Stripe webhook listener, only if the Stripe CLI is installed (use -NoStripe to skip it)

  Run from the repo root:   npm run dev:all        (or  .\scripts\dev.ps1 [-NoStripe])

  The Stripe CLI's webhook secret (whsec_...) is read with `stripe listen --print-secret` and handed to the
  backend window as an environment variable. It is never written to a file, so .env keeps no test secret.
  Real environment variables win over .env (backend/config.py), so the listener's secret is the one used.
#>
param([switch]$NoStripe)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "The backend virtualenv is missing. Run: cd backend; python -m venv venv; .\venv\Scripts\activate; pip install -r requirements-dev.txt" -ForegroundColor Red
    exit 1
}

function Test-PortFree([int]$port) {
    return -not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
foreach ($port in 8000, 3000) {
    if (-not (Test-PortFree $port)) {
        Write-Host "Port $port is already in use. Stop whatever is using it first (see AGENTS.md section 4, 'Free a stuck port')." -ForegroundColor Red
        exit 1
    }
}

$stripe = if ($NoStripe) { $null } else { Get-Command stripe -ErrorAction SilentlyContinue }
$secretLine = ""
if ($stripe) {
    $secret = (& stripe listen --print-secret 2>$null | Select-Object -First 1)
    if ($secret -and $secret.Trim().StartsWith("whsec_")) {
        $secretLine = "`$env:STRIPE_WEBHOOK_SECRET = '$($secret.Trim())'; "
    } else {
        Write-Host "Stripe CLI found, but it is not logged in. Run 'stripe login' once, then start again. Starting without the listener." -ForegroundColor Yellow
        $stripe = $null
    }
} elseif (-not $NoStripe) {
    Write-Host "Stripe CLI not installed: payments will not be marked paid locally. Install it from https://docs.stripe.com/stripe-cli (or pass -NoStripe to hide this)." -ForegroundColor Yellow
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'Nora backend'; Set-Location '$root\backend'; $secretLine& '$python' -m uvicorn main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'Nora frontend'; Set-Location '$root'; npm run dev"
if ($stripe) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'Stripe webhooks'; stripe listen --forward-to localhost:8000/payments/stripe/webhook"
}

Write-Host ""
Write-Host "Started. Open http://localhost:3000 (not the 192.168.x.x address). Close the windows to stop." -ForegroundColor Green
