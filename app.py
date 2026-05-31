#!/usr/bin/env python3
"""convert-to-webp2 — JPG/JPEG → WebP 무손실 변환 GUI (PySide6)."""

from __future__ import annotations

import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from converter import ConvertResult, convert_one, find_jpeg_files

# 자원 과소비 방지를 위해 동시 변환 개수를 제한한다 (코어 수와 무관하게 최대 5개).
MAX_WORKERS = 5


class Worker(QThread):
    """백그라운드 변환 스레드. ThreadPoolExecutor로 파일을 병렬 변환한다.

    libwebp 인코딩과 LANCZOS 리사이즈는 C 영역에서 GIL을 해제하므로
    스레드만으로도 멀티코어를 활용한다.
    """

    progress = Signal(int, int)        # done, total
    fileDone = Signal(object)          # ConvertResult
    finishedAll = Signal(int, int, bool)  # converted, total, cancelled
    fatalError = Signal(str)

    def __init__(
        self, target: Path, files: list[Path], max_dim: int | None, workers: int
    ) -> None:
        super().__init__()
        self._target = target
        self._files = files
        self._max_dim = max_dim
        self._workers = workers
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        out_dir = self._target / "webp"
        try:
            out_dir.mkdir(exist_ok=True)
        except OSError as e:
            self.fatalError.emit(f"출력 폴더를 만들 수 없습니다: {e}")
            return

        total = len(self._files)
        done = 0
        converted = 0
        cancelled_pending = False

        with ThreadPoolExecutor(max_workers=self._workers) as ex:
            futures = {
                ex.submit(convert_one, f, out_dir, self._max_dim): f
                for f in self._files
            }
            for fut in as_completed(futures):
                # 취소 요청 시: 아직 시작되지 않은 작업만 취소.
                # 진행 중(실행 중)인 작업은 끝까지 완료시켜 디스크 상태와 카운트를 일치시킨다.
                if self._cancel.is_set() and not cancelled_pending:
                    for pending in futures:
                        pending.cancel()
                    cancelled_pending = True

                if fut.cancelled():
                    continue

                res: ConvertResult = fut.result()
                done += 1
                if res.ok:
                    converted += 1
                self.fileDone.emit(res)
                self.progress.emit(done, total)

        self.finishedAll.emit(converted, total, self._cancel.is_set())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JPG/JPEG → WebP 변환기")
        self.resize(560, 480)

        self._target: Path | None = None
        self._files: list[Path] = []
        self._worker: Worker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- 폴더 선택 ---
        folder_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("변환할 JPG/JPEG가 들어있는 폴더를 선택하세요")
        self._select_btn = QPushButton("폴더 선택")
        self._select_btn.clicked.connect(self._select_folder)
        folder_row.addWidget(self._path_edit)
        folder_row.addWidget(self._select_btn)
        root.addLayout(folder_row)

        self._info_label = QLabel("폴더를 선택하면 파일 개수가 표시됩니다.")
        root.addWidget(self._info_label)

        # --- 해상도 옵션 ---
        res_row = QHBoxLayout()
        self._limit_check = QCheckBox("긴 축 최대 해상도 지정 (px)")
        self._limit_check.toggled.connect(self._on_limit_toggled)
        self._dim_spin = QSpinBox()
        self._dim_spin.setRange(1, 100000)
        self._dim_spin.setValue(4000)
        self._dim_spin.setSuffix(" px")
        self._dim_spin.setEnabled(False)
        res_row.addWidget(self._limit_check)
        res_row.addWidget(self._dim_spin)
        res_row.addStretch(1)
        root.addLayout(res_row)

        # --- 실행 버튼 ---
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("변환 시작")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start)
        self._cancel_btn = QPushButton("취소")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._cancel_btn)
        root.addLayout(btn_row)

        # --- 진행 표시 ---
        self._progress = QProgressBar()
        self._progress.setValue(0)
        root.addWidget(self._progress)

        self._status_label = QLabel("")
        root.addWidget(self._status_label)

        # --- 결과 로그 ---
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        root.addWidget(self._log, stretch=1)

    # ------------------------------------------------------------------
    # 폴더 / 옵션
    # ------------------------------------------------------------------

    def _select_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "변환할 폴더 선택")
        if not directory:
            return
        self._target = Path(directory)
        self._files = find_jpeg_files(self._target)
        self._path_edit.setText(directory)
        self._info_label.setText(f"JPG/JPEG {len(self._files)}개 발견")
        self._start_btn.setEnabled(bool(self._files))
        self._progress.setValue(0)
        self._status_label.setText("")
        self._log.clear()

    def _on_limit_toggled(self, checked: bool) -> None:
        self._dim_spin.setEnabled(checked)

    # ------------------------------------------------------------------
    # 변환 실행 / 취소
    # ------------------------------------------------------------------

    def _start(self) -> None:
        if not self._target or not self._files:
            return
        max_dim = self._dim_spin.value() if self._limit_check.isChecked() else None
        workers = min(MAX_WORKERS, os.cpu_count() or MAX_WORKERS)

        self._progress.setMaximum(len(self._files))
        self._progress.setValue(0)
        self._log.clear()
        self._set_running(True)

        self._worker = Worker(self._target, self._files, max_dim, workers)
        self._worker.progress.connect(self._on_progress)
        self._worker.fileDone.connect(self._on_file_done)
        self._worker.finishedAll.connect(self._on_finished)
        self._worker.fatalError.connect(self._on_fatal)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker:
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("취소 중… 진행 중인 파일을 마무리합니다.")
            self._worker.cancel()

    # ------------------------------------------------------------------
    # 워커 시그널 핸들러 (메인 스레드에서 실행됨)
    # ------------------------------------------------------------------

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setValue(done)
        self._status_label.setText(f"변환 중… {done}/{total}")

    def _on_file_done(self, res: ConvertResult) -> None:
        if res.ok:
            self._log.appendPlainText(
                f"✓ {res.name}  ({res.src_kb:.0f}KB → {res.dst_kb:.0f}KB)"
            )
        else:
            self._log.appendPlainText(f"✗ {res.name}  실패: {res.error}")

    def _on_finished(self, converted: int, total: int, cancelled: bool) -> None:
        self._set_running(False)
        self._worker = None
        verb = "취소됨" if cancelled else "완료"
        out = self._target / "webp" if self._target else Path("webp")
        self._status_label.setText(f"{verb}: 전체 {total}개 중 {converted}개 변환 완료")
        QMessageBox.information(
            self,
            verb,
            f"전체 {total}개 중 {converted}개 변환 완료\n저장 위치: {out}",
        )

    def _on_fatal(self, message: str) -> None:
        self._set_running(False)
        self._worker = None
        QMessageBox.critical(self, "오류", message)

    # ------------------------------------------------------------------
    # 상태 전환 / 종료
    # ------------------------------------------------------------------

    def _set_running(self, running: bool) -> None:
        self._select_btn.setEnabled(not running)
        self._start_btn.setEnabled(not running and bool(self._files))
        self._limit_check.setEnabled(not running)
        self._dim_spin.setEnabled(not running and self._limit_check.isChecked())
        self._cancel_btn.setEnabled(running)

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt 시그니처
        if self._worker and self._worker.isRunning():
            answer = QMessageBox.question(
                self,
                "변환 중",
                "변환이 진행 중입니다. 취소하고 종료할까요?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            self._worker.wait(5000)
        event.accept()


def main() -> None:
    import multiprocessing

    multiprocessing.freeze_support()  # PyInstaller + (향후) 멀티프로세스 대비 무해한 안전장치
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
