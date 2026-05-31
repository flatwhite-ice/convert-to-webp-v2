@echo off
REM Windows (cmd) 빌드 스크립트 — 탐색기에서 더블클릭으로 실행 가능.
REM 가상환경(.venv)을 만들어 의존성을 설치한 뒤 PyInstaller로 단독 실행 파일(.exe)을 생성한다.
setlocal
cd /d "%~dp0"

REM Python 런처(py) 우선, 없으면 python 사용
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py") else (set "PY=python")

%PY% --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo 오류: Python을 찾을 수 없습니다.
    echo   https://www.python.org/downloads/ 에서 Python 3.9 이상을 설치하세요.
    echo   설치 화면에서 "Add Python to PATH" 옵션을 반드시 체크하세요.
    goto :error
)

if not exist ".venv" (
    echo 가상환경 생성: .venv
    %PY% -m venv .venv
    if errorlevel 1 goto :error
)

set "VPY=.venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :error
"%VPY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error
"%VPY%" build.py
if errorlevel 1 goto :error

echo.
echo 배포 시 dist\convert-to-webp2-windows.zip 을 통째로 전달하세요.
echo.
pause
goto :eof

:error
echo.
echo 빌드 실패. 위 오류 메시지를 확인하세요.
echo.
pause
exit /b 1
