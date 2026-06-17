# QuantrixLabs LinkedIn Agent — local dev launcher
# Run from the project root:  .\start-dev.ps1

$root = Split-Path $MyInvocation.MyCommand.Path

Write-Host "Starting backend (FastAPI)..." -ForegroundColor Cyan
Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" `
              -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
              -WorkingDirectory "$root\backend"

Write-Host "Starting frontend (Vite)..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" `
              -ArgumentList "/k npm run dev" `
              -WorkingDirectory "$root\frontend"

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
