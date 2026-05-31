"""JPG/JPEG → WebP 무손실 변환 로직 (GUI 무의존).

GUI(app.py)와 분리해 둠으로써 단위 테스트와 워커 스레드에서 그대로 재사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_jpeg_files(directory: Path) -> list[Path]:
    """디렉토리 최상위의 JPG/JPEG 파일을 대소문자 구분 없이 수집(중복 제거)."""
    files: list[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.JPG", "*.JPEG", "*.Jpg", "*.Jpeg"):
        files.extend(directory.glob(ext))
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in sorted(files):
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    return unique


def _patch_webp_exif(path: Path) -> None:
    """Pillow가 제거한 'Exif\\x00\\x00' 접두사를 WebP EXIF 청크에 복원한다.

    WebP 스펙은 접두사 없는 TIFF 데이터를 권장하지만, Windows WIC 코덱 등
    다수의 도구가 'Exif\\x00\\x00' 접두사를 요구해 EXIF가 보이지 않는다.
    """
    data = bytearray(path.read_bytes())
    if len(data) < 12 or data[8:12] != b"WEBP":
        return

    pos = 12
    while pos + 8 <= len(data):
        chunk_id = bytes(data[pos : pos + 4])
        chunk_size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        padding = chunk_size % 2

        if chunk_id == b"EXIF":
            content = bytes(data[pos + 8 : pos + 8 + chunk_size])
            if not content.startswith(b"Exif\x00\x00"):
                new_content = b"Exif\x00\x00" + content
                new_size = len(new_content)
                new_chunk = (
                    b"EXIF"
                    + new_size.to_bytes(4, "little")
                    + new_content
                    + (b"\x00" if new_size % 2 else b"")
                )
                data[pos : pos + 8 + chunk_size + padding] = new_chunk
                data[4:8] = (len(data) - 8).to_bytes(4, "little")
            break

        pos += 8 + chunk_size + padding

    path.write_bytes(bytes(data))


def convert_file(src: Path, dst: Path, max_dim: int | None = None) -> None:
    """단일 파일을 무손실 WebP로 변환. EXIF/DPI 보존, 긴 쪽 max_dim 축소(업스케일 없음)."""
    from PIL import Image
    import piexif

    with Image.open(src) as img:
        dpi = img.info.get("dpi")

        # raw bytes 우선 사용 (piexif는 MakerNote 등 일부 태그를 손실시킴)
        exif_bytes: bytes | None = img.info.get("exif") or None
        if not exif_bytes:
            try:
                exif_bytes = piexif.dump(piexif.load(str(src)))
            except Exception:
                exif_bytes = None

        if max_dim is not None:
            w, h = img.size
            longer = max(w, h)
            if longer > max_dim:
                ratio = max_dim / longer
                img = img.resize((round(w * ratio), round(h * ratio)), Image.LANCZOS)

        save_kwargs: dict = {
            "lossless": True,
            "quality": 100,
            "method": 6,
        }
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        if dpi:
            save_kwargs["dpi"] = dpi

        img.save(dst, "WEBP", **save_kwargs)

    # Pillow가 제거한 'Exif\x00\x00' 접두사 복원 (Windows WIC 코덱 호환)
    if exif_bytes:
        _patch_webp_exif(dst)


@dataclass
class ConvertResult:
    """워커가 GUI로 돌려주는 단일 파일 변환 결과."""

    name: str
    src_kb: float
    dst_kb: float
    ok: bool
    error: str = ""


def convert_one(src: Path, out_dir: Path, max_dim: int | None) -> ConvertResult:
    """예외를 삼켜 결과 객체로 변환 — 워커 스레드/풀에서 안전하게 호출하기 위함."""
    dst = out_dir / (src.stem + ".webp")
    try:
        convert_file(src, dst, max_dim)
        src_kb = src.stat().st_size / 1024
        dst_kb = dst.stat().st_size / 1024
        return ConvertResult(src.name, src_kb, dst_kb, ok=True)
    except Exception as e:  # noqa: BLE001 — UI에 표시할 메시지로 변환
        return ConvertResult(src.name, 0.0, 0.0, ok=False, error=str(e))
