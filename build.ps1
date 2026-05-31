# Windows (PowerShell) 빌드 스크립트.
# 가상환경(.venv)을 만들어 의존성을 설치한 뒤 PyInstaller로 단독 실행 파일(.exe)을 생성한다.
#   사용법:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

if (-not (Test-Path ".venv")) {
    Write-Host "가상환경 생성: .venv"
    & $py -m venv .venv
}

$vpy = ".\.venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r requirements.txt pyinstaller
& $vpy build.py

Write-Host ""
Write-Host "배포 시 dist\convert-to-webp2-windows.zip 을 통째로 전달하세요."
