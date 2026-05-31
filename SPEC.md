# SPEC.md — convert-to-webp2 스펙 명세서

코드베이스 기준 구현 상태를 모두 담은 단일 참조 문서.

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| **앱 이름** | convert-to-webp2 |
| **실행 파일명** | `convert-to-webp2.exe` (Windows) / `convert-to-webp2` (macOS/Linux) |
| **목적** | JPG/JPEG 파일을 WebP(무손실)로 일괄 변환. EXIF·DPI 메타데이터 보존 |
| **대상 사용자** | 사진가 등 비개발자 — 파이썬/터미널 지식 없이 더블클릭으로 실행 |
| **주 배포 플랫폼** | Windows 데스크톱 (코드는 macOS/Linux 동작) |
| **현재 버전** | 1.0.0.0 |

---

## 2. 기능 명세

### 2.1 폴더 선택

- **UI**: "폴더 선택" 버튼 → `QFileDialog.getExistingDirectory()` 호출
- **저장**: 선택 경로를 `self._target` (`Path` 객체)에 저장, `QLineEdit`에 표시
- **부수 효과**: 파일 스캔 즉시 실행, 진행바·로그 초기화

### 2.2 파일 스캔 (`find_jpeg_files()`)

- **탐색 범위**: 선택 폴더 **최상위만** (재귀 없음)
- **검색 패턴**: `*.jpg`, `*.jpeg`, `*.JPG`, `*.JPEG`, `*.Jpg`, `*.Jpeg` (6가지)
- **중복 제거**: `Path.resolve()`로 실제 경로를 구해 `set`으로 처리 (심링크 포함)
- **결과 표시**: "JPG/JPEG N개 발견" — 0개면 변환 시작 버튼 비활성화

### 2.3 해상도 제한 옵션

- **UI 요소**: 체크박스 + 스핀박스 (기본값 **4000 px**, 범위 1 ~ 100,000)
- **체크 OFF** (기본): `max_dim=None` → 원본 해상도 그대로
- **체크 ON**: 긴 축이 입력값을 초과할 때만 **LANCZOS** 필터로 비율 유지 축소
  - 업스케일 없음 — 원본이 지정값보다 작으면 변환 없이 통과
  - 변환 공식: `ratio = max_dim / max(w, h)`, 새 크기 = `(round(w*ratio), round(h*ratio))`
  - ⚠️ **이 경로는 무손실이 아니다** — 축소가 일어나면 픽셀이 재계산되므로 2.4의 무손실 보장은 적용되지 않는다. 무손실 결과가 필요하면 옵션을 끈 채 변환할 것.

#### 변환/리사이즈 순서 (해상도 옵션 켤 때만 활성화)

해상도 지정 체크박스를 켜면 라디오버튼 2개가 활성화된다:

| 선택지 | 동작 | 비고 |
|--------|------|------|
| **리사이즈 후 변환** (기본) | 디코딩 → LANCZOS 축소 → WebP 인코딩 | 더 빠름 (작아진 이미지를 인코딩) |
| **변환 후 리사이즈** | 풀해상도 무손실 WebP 저장 → 다시 열어 축소·재저장 | 중간 산출물을 거침 |

> WebP가 무손실이라 두 순서의 **최종 픽셀은 동일**하다(실측 확인: `ImageChops.difference` → 차이 없음). 처리 순서와 속도만 다르며 사용자 선택 옵션으로 제공한다. 해상도 옵션이 꺼져 있으면 라디오는 비활성화되고 순서는 의미가 없다(`resize_after_convert`는 `max_dim`이 있을 때만 적용).
- **변환 중**: 옵션 변경 불가 (비활성화)

### 2.4 WebP 변환 파라미터

모든 변환은 **무손실 고정**:

```python
save_kwargs = {
    "lossless": True,   # 무손실 인코딩 (이 값이 무손실을 결정)
    "quality":  100,    # 무손실 모드에서는 "압축 노력치"(0=빠름/큼, 100=느림/작음). 화질과 무관
    "method":   6,      # 인코딩 알고리즘 최적화 수준 (0~6, 높을수록 느리지만 작음)
}
```

> **주의 — "무손실"의 정확한 의미**
> - 무손실을 보장하는 것은 `lossless=True` 단 하나다. `quality=100`은 무손실 모드에서 화질이 아니라 **압축 노력치**를 뜻한다(libwebp 사양).
> - "무손실"은 **원본 무손실이 아니라 "변환 단계 무손실"**이다. 소스 JPEG 자체가 이미 손실 압축된 데이터이며, 본 도구는 그 JPEG이 디코딩한 RGB 픽셀을 손실 없이 WebP로 담는다.
> - **검증**: 임의 노이즈 JPEG → 변환 후, JPEG 디코딩 픽셀과 WebP 디코딩 픽셀이 바이트 단위로 동일함을 실측 확인(`ImageChops.difference` → 차이 없음).
> - **예외**: 2.3의 해상도 제한(`max_dim`)이 적용되면 LANCZOS 축소로 픽셀이 바뀌므로 그 출력은 무손실이 아니다.

### 2.5 EXIF 처리 (4단계)

| 단계 | 동작 | 비고 |
|------|------|------|
| ① raw bytes 추출 | `img.info.get("exif")` | MakerNote 등 비표준 태그까지 완전 보존 |
| ② piexif 폴백 | `piexif.dump(piexif.load(src))` | ①이 없을 때만 실행; 예외 발생 시 `exif_bytes=None` |
| ③ WebP 저장 시 삽입 | `save_kwargs["exif"] = exif_bytes` | bytes가 있을 때만 |
| ④ 접두사 복원 (`_patch_webp_exif`) | EXIF 청크에 `Exif\x00\x00` 접두사 추가 | Pillow가 저장 후 제거하므로 후처리 필요 |

**접두사 복원 이유**: WebP 스펙은 접두사 없는 TIFF 데이터를 권장하나, Windows 탐색기·WIC 코덱 등 다수 도구가 `Exif\x00\x00` 접두사를 요구해 메타데이터가 보이지 않는 문제 발생.

**복원 방식**: 저장된 파일의 RIFF/WEBP 바이너리를 직접 파싱 → EXIF 청크 위치 찾기 → 접두사 미존재 시 삽입 → 청크 크기·RIFF 전체 크기 재계산 후 덮어쓰기.

### 2.6 DPI 및 ICC 컬러 프로파일 보존

```python
dpi = img.info.get("dpi")
if dpi:
    save_kwargs["dpi"] = dpi

icc_profile = img.info.get("icc_profile")
if icc_profile:
    save_kwargs["icc_profile"] = icc_profile
```

- **DPI**: 원본 해상도 정보가 있으면 유지.
- **ICC 프로파일**: Adobe RGB·Display P3 등 광색역 프로파일을 보존. 누락 시 뷰어가 sRGB로 오인해 색이 틀어지므로 사진가용 도구에서 필수. (검증: ICC 포함 JPEG → 변환 WebP에 ICC 청크 존재 실측 확인)

### 2.7 출력 경로 규칙

| 항목 | 규칙 |
|------|------|
| 출력 폴더 | `{선택한 폴더}/webp/` |
| 출력 파일명 | `{원본 stem}.webp` |
| 폴더 생성 | 없으면 생성, 있으면 재사용 (`exist_ok=True`) |
| 파일 충돌 | 덮어쓰기 |

예) `/photos/IMG_001.jpg` → `/photos/webp/IMG_001.webp`

### 2.8 병렬 처리

```python
MAX_WORKERS = 5                                   # 하드 캡 (app.py 상수)
workers = min(MAX_WORKERS, os.cpu_count() or MAX_WORKERS)
```

| 시스템 코어 수 | 실제 동시 변환 수 |
|:---:|:---:|
| 1 | 1 |
| 2 | 2 |
| 4 | 4 |
| 8+ | 5 |
| 감지 실패 | 5 |

- libwebp 인코딩과 LANCZOS 리사이즈는 **C 영역에서 GIL 해제** → 스레드만으로도 멀티코어 활용 가능

### 2.9 취소 동작

1. "취소" 버튼 클릭 → `Worker._cancel` (`threading.Event`) 설정
2. `as_completed()` 루프에서 플래그 감지 시:
   - **미시작 작업**: `Future.cancel()` 호출 → `fut.cancelled() == True` → 카운터 스킵
   - **실행 중 작업**: 완료될 때까지 계속 실행 (디스크 상태·카운트 일치 보장)
3. 모든 처리 완료 후 `finishedAll` 시그널에 `cancelled=True`로 발행

### 2.10 완료 요약 및 폴더 열기

변환(또는 취소) 종료 시 Yes/No 질문 다이얼로그를 표시한다:

```
{완료 | 취소됨}
전체 N개 중 M개 변환 완료
저장 위치: {target}/webp

폴더를 열까요?   [예] [아니오]
```

- 기본 버튼은 **예**.
- **예** 선택 시 출력 폴더(`{target}/webp`)를 OS 기본 파일 탐색기로 연다.
- 구현: `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` — macOS·Windows·Linux를 Qt가 일괄 처리(별도 subprocess 분기 없음). 폴더가 실제 존재할 때만 연다.

### 2.11 파일별 로그 형식

```
✓ {파일명}  ({원본KB:.0f}KB → {결과KB:.0f}KB)   # 성공
✗ {파일명}  실패: {에러 메시지}                  # 실패
```

### 2.12 종료 보호

변환 중 창 닫기 시 확인 다이얼로그 표시:
- **예**: `Worker.cancel()` + `Worker.wait(5000ms)` 후 종료
- **아니오**: 종료 취소, 변환 계속

---

## 3. 기술 스택 및 의존성

### 3.1 런타임 의존성 (`requirements.txt`)

| 패키지 | 최소 버전 | 용도 |
|--------|:---------:|------|
| `PySide6` | 6.6.0 | Qt GUI 프레임워크 — `QMainWindow`, `QThread`, `Signal` 등 |
| `Pillow` | 10.0.0 | 이미지 열기·저장, WebP 인코딩, LANCZOS 리사이즈 |
| `piexif` | 1.1.3 | EXIF 폴백 추출 (raw bytes 없을 때) |

### 3.2 Python 버전

- **최소**: Python **3.10**
- **이유**: `PySide6>=6.6.0`이 Python 3.9 지원 중단
- **검사 위치**: `build.py` `main()` 첫 줄, `build.sh`/`build.bat`/`build.ps1` 런타임 검사

### 3.3 빌드 의존성

- **PyInstaller**: 단독 실행 파일/폴더 생성 (`build.py`가 설치 여부 확인)

---

## 4. 아키텍처

### 4.1 파일 책임 분리

| 파일 | 책임 |
|------|------|
| `converter.py` | GUI 무의존 순수 변환 로직. `find_jpeg_files`, `convert_file`, `convert_one`, `_patch_webp_exif`, `ConvertResult` |
| `app.py` | GUI + 스레딩 제어. `Worker(QThread)`, `MainWindow(QMainWindow)`, `main()` |
| `build.py` | PyInstaller 자동화 + 플랫폼별 옵션 + zip 압축 |
| `build.sh` | macOS/Linux 빌드 진입점 (venv 생성·검증 → `build.py` 호출) |
| `build.bat` | Windows cmd 빌드 진입점 (더블클릭 가능) |
| `build.ps1` | Windows PowerShell 빌드 진입점 |

`converter.py`는 GUI 라이브러리 임포트가 없어 단독 단위 테스트 가능.

### 4.2 스레딩 모델

```
MainWindow (Qt 메인 스레드)
  │
  ├─ _start() 호출
  │     └─ Worker(QThread) 생성 & 시작
  │
  └─ 시그널 슬롯 (Qt 큐 경유, 메인 스레드에서 실행)
        ├─ _on_progress()    ← progress 시그널
        ├─ _on_file_done()   ← fileDone 시그널
        ├─ _on_finished()    ← finishedAll 시그널
        └─ _on_fatal()       ← fatalError 시그널

Worker (QThread — 백그라운드 스레드)
  │
  └─ ThreadPoolExecutor(max_workers ≤ 5)
        ├─ convert_one(file1, ...)   ← 워커 스레드 1
        ├─ convert_one(file2, ...)   ← 워커 스레드 2
        └─ convert_one(fileN, ...)   ← 워커 스레드 N
              (libwebp/LANCZOS: C 영역, GIL 해제)
```

**총 스레드 수**: 메인 1 + Worker 1 + 풀 최대 5 = **최대 7개**

### 4.3 Signal 명세 (Worker → MainWindow)

| Signal | Payload | 발행 시점 |
|--------|---------|----------|
| `progress` | `(int done, int total)` | 파일 1개 완료마다 |
| `fileDone` | `ConvertResult` | 파일 1개 완료마다 (성공/실패 무관) |
| `finishedAll` | `(int converted, int total, bool cancelled)` | 전체 처리 완료 또는 취소 후 |
| `fatalError` | `str message` | 출력 폴더 생성 실패 시 |

### 4.4 ConvertResult 데이터클래스

```python
@dataclass
class ConvertResult:
    name:   str    # 원본 파일명 (예: "IMG_001.jpg")
    src_kb: float  # 원본 크기 (KB)
    dst_kb: float  # 변환 후 크기 (KB); 실패 시 0.0
    ok:     bool   # 성공 여부
    error:  str = ""  # 실패 사유 (ok=False일 때만)
```

---

## 5. 빌드 및 배포

### 5.1 플랫폼별 빌드 명령

| 플랫폼 | 명령 |
|--------|------|
| macOS / Linux | `./build.sh` |
| macOS / Linux (Python 지정) | `PYTHON=python3.12 ./build.sh` |
| Windows cmd | `build.bat` (탐색기 더블클릭 가능) |
| Windows PowerShell | `powershell -ExecutionPolicy Bypass -File build.ps1` |
| 직접 실행 | `python build.py` (Python 3.10+, 의존성 설치 필요) |

**빌드 스크립트 공통 흐름**:
1. Python 3.10+ 버전 검사 → 미달 시 오류·종료
2. `.venv` 건강 검사 (버전·pip 동작) → 문제 시 삭제 후 재생성
3. pip 업그레이드 + `requirements.txt` + PyInstaller 설치
4. `build.py` 호출

### 5.2 PyInstaller 옵션 및 선택 이유

| 옵션 | 값 | 이유 |
|------|----|------|
| `--onedir` | (기본 출력 형태) | 자가압축해제 없음 → 빠른 시작, 백신/SmartScreen 오탐 감소 |
| `--windowed` | — | 콘솔 창 표시 안 함 (GUI 전용) |
| `--noupx` | — | UPX 압축 미사용 → 보안 도구 오탐 감소 |
| `--noconfirm` + `--clean` | — | 빌드 자동화 편의 |
| `--version-file version.txt` | Windows only | 파일 탐색기 → 파일 속성에 버전·제품명 표시 |
| `--icon icon.ico / icon.icns` | 파일 있을 때만 | 아이콘 자동 감지 |

### 5.3 산출물 구조

실행 폴더는 OS별로 구분된 이름(`convert-to-webp2-<os>`)으로 만들어진다. 실행 파일 이름 자체는 `convert-to-webp2`로 유지된다.

```
dist/
├── convert-to-webp2-windows/       ← 실행 폴더 (Windows 빌드, OS 접미사)
│   ├── convert-to-webp2.exe        ← 메인 실행 파일 (이름 유지)
│   └── _internal/                  ← PySide6, Pillow, numpy 등 의존 라이브러리
│
└── convert-to-webp2-windows.zip    ← 배포용 압축본 (풀면 convert-to-webp2-windows/ 구조 유지)
```

(macOS 빌드 시 `convert-to-webp2-macos/`, Linux 빌드 시 `convert-to-webp2-linux/`. 산출물은 빌드한 OS에서만 생성됨.)

**구현**: PyInstaller는 `--name convert-to-webp2`로 빌드(실행 파일명 유지)한 뒤, `dist/convert-to-webp2/`를 `dist/convert-to-webp2-<os>/`로 이름 변경하고 그 폴더를 zip으로 압축한다(이전 빌드 잔여물은 제거 후 대체).

**배포 방법**: zip 전달 → 압축 해제 → `convert-to-webp2-<os>/` 폴더에서 실행 파일 실행.

### 5.4 version.txt (Windows 파일 속성 메타데이터)

| 항목 | 값 |
|------|-----|
| FileVersion | 1.0.0.0 |
| ProductVersion | 1.0.0.0 |
| FileDescription | JPG/JPEG to WebP Converter |
| ProductName | JPG to WebP Converter |
| InternalName | convert-to-webp2 |
| OriginalFilename | convert-to-webp2.exe |
| LegalCopyright | (비어 있음) |

---

## 6. 범위 밖 (Non-goals)

| 항목 | 이유 / 비고 |
|------|------------|
| PNG / TIFF 등 JPG 외 입력 포맷 | 스코프 제한 |
| 하위 폴더 재귀 탐색 | 단순성 유지 |
| 손실 압축 품질 슬라이더 | 무손실 고정 (전문 사진가 용도) |
| 변환 결과 미리보기 / 썸네일 | UI 복잡도·성능 영향 |
| 코드 서명 (SmartScreen 경고 완전 제거) | Azure Trusted Signing / EV 인증서 필요 |
| 단독 단일 exe (onefile) | `--onedir` + zip으로 대체 (시작 빠름, 오탐 적음) |
