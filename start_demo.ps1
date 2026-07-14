# Запускает всё для демо в пяти окнах: API, бот, веб-панель, мобильное (Expo), ngrok.
# Использование: .\start_demo.ps1  (компьютер оставить включённым, окна не закрывать)
$root = $PSScriptRoot

# ngrok не в PATH — берём с рабочего стола; если переложите, поправьте путь
$ngrok = "C:\Users\User\Desktop\ngrok.exe"
if (-not (Test-Path $ngrok)) { $ngrok = "ngrok" }

Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'API :8000'; cd '$root'; .\.venv\Scripts\python manage.py runserver"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'BOT'; cd '$root'; .\.venv\Scripts\python manage.py runbot"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'PANEL :3001'; cd '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'MOBILE (Expo)'; cd '$root\mobile'; npm start"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'NGROK'; & '$ngrok' start --all"

Write-Host ""
Write-Host "Запущено 5 окон:" -ForegroundColor Green
Write-Host "  API :8000, BOT, PANEL :3001, MOBILE (Expo), NGROK"
Write-Host ""
Write-Host "Дальше:"
Write-Host "1. Мобильное приложение: в окне MOBILE появится QR — отсканируйте его в Expo Go."
Write-Host "   (Телефон и компьютер должны быть в одной Wi-Fi сети.)"
Write-Host "2. Веб-панель: в окне NGROK скопируйте https-адрес туннеля на :3001."
Write-Host "3. Админка: https://crack-troll-maximum.ngrok-free.app/admin/"
Write-Host "4. Не закрывайте окна и не давайте компьютеру уснуть."
