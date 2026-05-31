# Windows (PowerShell) 빌드 스크립트.
# 가상환경(.venv)을 만들어 의존성을 설치한 뒤 PyInstaller로 단독 실행 파일(.exe)을 생성한다.
#   사용법:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

if (-not (Get-Command $py -ErrorAction SilentlyContinue)) {
    Write-Error "오류: Python을 찾을 수 없습니다. https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요."
    exit 1
}

# Python 3.10 미만 확인 (PySide6 6.6+ 요구사항)
$pyVerStr = & $py -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))"
$pyVer = [System.Version]$pyVerStr
if ($pyVer -lt [System.Version]"3.10") {
    $fullVer = & $py -c "import sys; print(sys.version.split()[0])"
    Write-Host ""
    Write-Host "오류: Python 3.10 이상이 필요합니다. 현재: $fullVer" -ForegroundColor Red
    Write-Host "  PySide6 6.6+ 는 Python 3.9 를 지원하지 않습니다." -ForegroundColor Red
    Write-Host "  https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요." -ForegroundColor Red
    exit 1
}

$vpy = ".\.venv\Scripts\python.exe"

# 기존 venv 가 있으면 Python 버전과 pip 동작 여부 확인, 문제가 있으면 삭제 후 재생성
if ((Test-Path ".venv") -and (Test-Path $vpy)) {
    & $vpy -c "import sys, pip; assert sys.version_info >= (3,10)" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "기존 가상환경이 비정상 상태입니다. 삭제 후 재생성합니다."
        Remove-Item -Recurse -Force ".venv"
    }
}

if (-not (Test-Path ".venv")) {
    Write-Host "가상환경 생성: .venv"
    & $py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Recurse -Force ".venv" -ErrorAction SilentlyContinue
        Write-Host ""
        Write-Host "오류: 가상환경 생성에 실패했습니다." -ForegroundColor Red
        Write-Host "  Python 을 재설치하거나 아래 링크에서 새로 설치해 보세요." -ForegroundColor Red
        Write-Host "  https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
}
& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r requirements.txt pyinstaller
& $vpy build.py

Write-Host ""
Write-Host "배포 시 dist\convert-to-webp2-windows.zip 을 통째로 전달하세요."
