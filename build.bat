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
    echo   https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요.
    echo   설치 화면에서 "Add Python to PATH" 옵션을 반드시 체크하세요.
    goto :error
)

REM Python 3.10 미만 확인 (PySide6 6.6+ 요구사항)
for /f %%V in ('%PY% -c "import sys; print(sys.version_info.major * 100 + sys.version_info.minor)"') do set "PY_VER=%%V"
if not defined PY_VER (
    echo 오류: Python 버전을 확인할 수 없습니다.
    goto :error
)
if %PY_VER% LSS 310 (
    for /f %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PY_STR=%%V"
    echo.
    echo 오류: Python 3.10 이상이 필요합니다. 현재: %PY_STR%
    echo   PySide6 6.6+ 는 Python 3.9 를 지원하지 않습니다.
    echo   https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요.
    echo   설치 화면에서 "Add Python to PATH" 옵션을 반드시 체크하세요.
    goto :error
)

set "VPY=.venv\Scripts\python.exe"

REM 기존 venv 가 있으면 Python 버전과 pip 동작 여부 확인, 문제가 있으면 삭제 후 재생성
if exist "%VPY%" (
    "%VPY%" -c "import sys, pip; assert sys.version_info >= (3,10)" >nul 2>nul
    if errorlevel 1 (
        echo 기존 가상환경이 비정상 상태입니다. 삭제 후 재생성합니다.
        rmdir /s /q .venv
    )
)

if not exist ".venv" (
    echo 가상환경 생성: .venv
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo 오류: 가상환경 생성에 실패했습니다.
        echo   Python 을 재설치하거나 아래 링크에서 새로 설치해 보세요.
        echo   https://www.python.org/downloads/
        goto :error
    )
)
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
