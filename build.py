#!/usr/bin/env python3
"""PyInstaller로 단독 실행 폴더(onedir)를 빌드하고 zip으로 압축한다.

사용법:
    pip install -r requirements.txt pyinstaller
    python build.py

결과:
    dist/convert-to-webp2-<os>/       실행 폴더 (exe + _internal/ 라이브러리, OS별 구분)
    dist/convert-to-webp2-<os>.zip    배포용 압축본

onedir 방식은 자가압축해제가 없어 시작이 빠르고 백신/SmartScreen 휴리스틱에
덜 걸린다. 단, exe와 _internal/ 폴더는 항상 함께 있어야 하므로 zip으로 배포한다.
(.exe/.app 등 산출물은 빌드한 OS에서만 만들어진다.)
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

APP_NAME = "convert-to-webp2"
ENTRY = "app.py"


def _platform_tag() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _force_rmtree(path: Path) -> None:
    """shutil.rmtree 가 깨진 심볼릭 링크/reparse point/읽기전용 파일에 막히지 않도록 보강.

    이전 빌드(특히 다른 OS)의 잔재로 dist 폴더에 broken symlink 가 남아 있으면
    Windows 에서 os.walk 가 WinError 1920 으로 죽는다. onerror 콜백에서 직접
    unlink/rmdir 로 다시 시도해 강제로 비운다.
    """
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
        except OSError:
            pass
        try:
            os.unlink(p)        # 파일/심볼릭 링크 (깨진 링크 포함)
            return
        except (OSError, IsADirectoryError):
            pass
        try:
            os.rmdir(p)         # 비어있는 디렉터리
        except OSError:
            pass

    shutil.rmtree(path, onerror=_onerror)


def _build_options(root: Path) -> list[str]:
    options = [
        "--onedir",      # 폴더 형태 (자가압축해제 없음)
        "--windowed",    # 콘솔 창 없이 GUI만 (Windows/macOS)
        "--noconfirm",   # 기존 산출물 덮어쓰기
        "--clean",
        "--noupx",       # UPX 압축 비활성화 (백신 오탐 감소)
        "--name", APP_NAME,
    ]
    # Windows: 버전 메타데이터 → 파일 속성에 제품명/버전 표기, 신뢰도 향상
    if sys.platform == "win32":
        version_file = root / "version.txt"
        if version_file.exists():
            options += ["--version-file", str(version_file)]
    # 아이콘은 있을 때만 적용 (Windows=.ico, macOS=.icns)
    icon = root / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    if icon.exists():
        options += ["--icon", str(icon)]
    return options


def main() -> int:
    if sys.version_info < (3, 10):
        print(
            f"오류: Python 3.10 이상이 필요합니다. 현재: {sys.version.split()[0]}",
            file=sys.stderr,
        )
        print("  PySide6 6.6+ 는 Python 3.9 를 지원하지 않습니다.", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parent
    entry = root / ENTRY
    if not entry.exists():
        print(f"오류: 진입점 {entry} 을(를) 찾을 수 없습니다.", file=sys.stderr)
        return 1

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("오류: PyInstaller가 설치되지 않았습니다.", file=sys.stderr)
        print("  pip install pyinstaller 를 실행하세요.", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-m", "PyInstaller", *_build_options(root), str(entry)]
    print("실행:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        return result.returncode

    tag = _platform_tag()
    src_bundle = root / "dist" / APP_NAME              # PyInstaller 출력 (exe 이름 유지)
    final_bundle = root / "dist" / f"{APP_NAME}-{tag}"  # 최종 폴더 (OS 접미사)

    if not src_bundle.is_dir():
        print(f"경고: 빌드 폴더 {src_bundle} 를 찾지 못해 압축을 건너뜁니다.", file=sys.stderr)
        return 0

    # OS 접미사 폴더로 이름 변경 (이전 빌드 잔여물은 제거 후 대체)
    # exists() 는 broken symlink 에서 False 를 반환하므로 is_symlink() 도 확인
    if final_bundle.exists() or final_bundle.is_symlink():
        _force_rmtree(final_bundle)
    src_bundle.rename(final_bundle)

    # dist/convert-to-webp2-<os>/ 폴더를 통째로 zip → 풀면 동일 폴더 구조 유지
    archive = shutil.make_archive(
        str(final_bundle), "zip",
        root_dir=final_bundle.parent, base_dir=final_bundle.name,
    )
    print("\n빌드 완료")
    print(f"  실행 폴더 → {final_bundle}")
    print(f"  배포 zip  → {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
