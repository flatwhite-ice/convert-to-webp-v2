#!/usr/bin/env bash
# Linux / macOS 빌드 스크립트.
# 가상환경(.venv)을 만들어 의존성을 설치한 뒤 PyInstaller로 단독 실행 파일을 생성한다.
#
# 사용법:
#   ./build.sh                        기본 (python3)
#   PYTHON=python3.12 ./build.sh      Python 버전을 직접 지정
#
# macOS에서 python3 가 구버전(3.9 등)을 가리키는 경우:
#   1) 설치된 버전 확인:  ls /usr/local/bin/python3* /opt/homebrew/bin/python3* 2>/dev/null
#   2) Homebrew로 설치:   brew install python@3.12
#      설치 후:           PYTHON=python3.12 ./build.sh
#   3) python.org 에서 직접 설치: https://www.python.org/downloads/
#      설치 후:           PYTHON=python3.12 ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "오류: '$PY' 를 찾을 수 없습니다. Python 3.10+ 를 설치하세요." >&2
    exit 1
fi

# PySide6 6.6+ 는 Python 3.10 미만 미지원.
PY_VER=$("$PY" -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)' 2>/dev/null)
if [ -z "$PY_VER" ] || [ "$PY_VER" -lt 310 ]; then
    ACTUAL_VER=$("$PY" -c 'import sys; print(sys.version.split()[0])' 2>/dev/null || echo "알 수 없음")
    echo "오류: Python 3.10 이상이 필요합니다. 현재: $ACTUAL_VER" >&2
    echo "" >&2
    echo "  macOS 시스템 기본 python3 가 구버전을 가리키는 경우:" >&2
    echo "  1) 설치된 버전 확인:" >&2
    echo "       ls /usr/local/bin/python3* /opt/homebrew/bin/python3* 2>/dev/null" >&2
    echo "  2) Homebrew 로 최신 Python 설치 (권장):" >&2
    echo "       brew install python@3.12" >&2
    echo "  3) 설치 후 이 스크립트를 다시 실행:" >&2
    echo "       PYTHON=python3.12 ./build.sh" >&2
    exit 1
fi

VENV=".venv"
VPY="$VENV/bin/python"

# 기존 venv 가 있으면 Python 버전과 pip 동작 여부를 확인하고, 문제가 있으면 삭제 후 재생성.
if [ -d "$VENV" ] && [ -f "$VPY" ]; then
    VENV_VER=$("$VPY" -c 'import sys; print(sys.version_info.major * 100 + sys.version_info.minor)' 2>/dev/null || echo "0")
    if [ "$VENV_VER" -lt 310 ]; then
        echo "기존 가상환경이 Python $("$VPY" --version 2>&1 | awk '{print $2}') 으로 생성되어 있습니다. 삭제 후 재생성합니다."
        rm -rf "$VENV"
    elif ! "$VPY" -m pip --version >/dev/null 2>&1; then
        echo "기존 가상환경에 pip 가 없습니다. 삭제 후 재생성합니다."
        rm -rf "$VENV"
    fi
fi

if [ ! -d "$VENV" ]; then
    echo "가상환경 생성: $VENV"
    if ! "$PY" -m venv "$VENV" 2>/dev/null; then
        rm -rf "$VENV"
        echo "오류: 가상환경 생성에 실패했습니다. (사용 중인 Python: $("$PY" --version))" >&2
        echo "" >&2
        echo "  macOS 26 Tahoe 등 최신 OS 에서 Homebrew Python 의 pyexpat 이" >&2
        echo "  시스템 libexpat 과 충돌해 pip 부트스트랩이 실패하는 경우입니다." >&2
        echo "" >&2
        echo "  해결 방법:" >&2
        echo "  1) Homebrew expat 설치 후 Python 재빌드 (권장):" >&2
        echo "       brew install expat" >&2
        echo "       brew reinstall python@3.12" >&2
        echo "       PYTHON=python3.12 ./build.sh" >&2
        echo "  2) python.org 공식 인스톨러 사용 (자체 libexpat 포함):" >&2
        echo "       https://www.python.org/downloads/" >&2
        echo "       설치 후: PYTHON=python3.12 ./build.sh" >&2
        exit 1
    fi
fi

"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -r requirements.txt pyinstaller
"$VPY" build.py
