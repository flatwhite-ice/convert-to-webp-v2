# FEATURES — convert-to-webp2

사진가용 JPG/JPEG → WebP 무손실 변환기 (Windows GUI). 현재 구현된 기능 목록.

## 변환 기능 (`converter.py`)

- **JPG/JPEG 스캔** — 선택 폴더 최상위의 `*.jpg`, `*.jpeg`를 대소문자 구분 없이 수집하고 중복 제거. (하위 폴더 재귀 없음)
- **무손실 WebP 인코딩** — `lossless=True`, `quality=100`, `method=6`으로 픽셀 완전 보존.
- **EXIF 보존**
  - 1순위: 원본 raw EXIF bytes(`img.info["exif"]`) 사용 — MakerNote 등 비표준 태그까지 보존.
  - 2순위(폴백): `piexif`로 추출.
  - 저장 후 `Exif\x00\x00` 접두사 복원(`_patch_webp_exif`) → Windows 탐색기/WIC 코덱에서 EXIF 정상 인식.
- **DPI 보존** — 원본 DPI 정보가 있으면 유지.
- **ICC 컬러 프로파일 보존** — Adobe RGB/Display P3 등 광색역 프로파일을 유지(누락 시 뷰어가 sRGB로 오인해 색이 틀어짐).
- **긴 축 해상도 지정(선택)** — 긴 축 최대 픽셀을 지정하면 비율 유지한 채 `LANCZOS`로 축소. 지정값보다 작은 이미지는 업스케일하지 않음.
- **출력 위치** — 선택한 폴더 하위에 `webp/` 폴더 생성, 파일명은 `<원본>.webp`.

## GUI (`app.py`, PySide6)

- **폴더 선택** — 다이얼로그로 폴더 선택, 경로 표시.
- **파일 개수 표시** — 선택 즉시 "JPG/JPEG N개 발견" 표시.
- **해상도 옵션** — "긴 축 최대 해상도 지정 (px)" 체크박스 + 스핀박스(기본 4000px). 체크 해제 시 원본 해상도 유지.
- **변환/리사이즈 순서 선택** — 해상도 옵션을 켜면 "리사이즈 후 변환(기본·빠름)" / "변환 후 리사이즈" 라디오버튼이 활성화. WebP가 무손실이라 두 순서의 최종 픽셀은 동일(속도만 차이).
- **진행 표시** — 프로그레스바 + "변환 중… done/total" 상태 텍스트 + 파일별 결과 로그(원본KB→결과KB / 실패 사유).
- **취소** — 취소 버튼 클릭 시 아직 시작되지 않은 작업은 취소, 진행 중인 파일만 마무리(디스크 상태와 카운트 일치).
- **완료 요약 + 폴더 열기** — 종료 시 "전체 N개 중 M개 변환 완료" + 저장 위치와 함께 "폴더를 열까요?" 질문 표시. "예" 선택 시 출력 폴더를 OS 파일 탐색기로 연다(`QDesktopServices`).
- **종료 보호** — 변환 중 창을 닫으면 취소 후 종료 여부 확인.
- **UI 무프리징** — 변환은 백그라운드 스레드에서 수행, 시그널로 메인 스레드 갱신.

## 병렬 처리

- **ThreadPoolExecutor** 기반 병렬 변환. libwebp 인코딩/LANCZOS가 C 영역에서 GIL을 해제하므로 스레드로도 멀티코어 활용.
- **동시 실행 상한 5개**(`MAX_WORKERS = 5`) — 코어 수가 많아도 5개까지만 동시 변환해 자원 과소비 방지(코어가 더 적으면 코어 수에 맞춤).

## 빌드 / 배포

- **onedir 패키징** (`build.py`) — `--onedir --windowed --noupx`. 실행 폴더를 생성한 뒤 OS별 이름(`dist/convert-to-webp2-<os>/`: `exe` + `_internal/`)으로 변경하고 `dist/convert-to-webp2-<os>.zip`으로 자동 압축. 실행 파일 이름은 `convert-to-webp2` 유지.
- **SmartScreen/백신 오탐 완화** — 자가압축해제 없는 onedir, UPX 미사용, Windows 버전 메타데이터(`version.txt`), 아이콘 자동 감지(`icon.ico`/`icon.icns`가 있을 때).
- **크로스플랫폼 빌드 스크립트** — `build.sh`(Linux/macOS), `build.bat`(Windows, 더블클릭 가능), `build.ps1`(PowerShell). 각자 `.venv` 구성 후 의존성 설치 → `build.py` 호출. 모두 스크립트 위치 기준으로 동작.
- **의존성** (`requirements.txt`) — PySide6, Pillow, piexif.

## 미구현 / 범위 외

- 단독 단일 exe(onefile) — onedir+zip로 대체.
- 코드 서명(SmartScreen 경고 완전 제거) — 미적용(Azure Trusted Signing/EV 인증서 필요).
- JPG 외 입력 포맷, 하위 폴더 재귀, 손실 압축 품질 조절, 결과 미리보기.
