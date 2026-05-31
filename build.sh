#!/usr/bin/env bash
# Linux / macOS 빌드 스크립트.
# 가상환경(.venv)을 만들어 의존성을 설치한 뒤 PyInstaller로 단독 실행 파일을 생성한다.
#   사용법:  ./build.sh        (필요시  PYTHON=python3.12 ./build.sh)
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "오류: '$PY' 를 찾을 수 없습니다. Python 3.9+ 를 설치하세요." >&2
    exit 1
fi

VENV=".venv"
if [ ! -d "$VENV" ]; then
    echo "가상환경 생성: $VENV"
    "$PY" -m venv "$VENV"
fi

VPY="$VENV/bin/python"
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -r requirements.txt pyinstaller
"$VPY" build.py
