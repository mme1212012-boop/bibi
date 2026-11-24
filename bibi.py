from __future__ import annotations

import queue
import re
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from updater import (
    INSTALLER_DOWNLOAD_URL,
    ReleaseUpdate,
    check_latest_update,
    download_update,
    launch_installer,
)
from water_sort import MAX_SEARCH_STATES, Move, parse_tubes, solve_water_sort
from water_sort_automation import execute_moves, parse_tube_positions
from water_sort_vision import (
    BoardDetectionError,
    annotate_water_sort_guidance,
    detect_water_sort_board,
)
from version import APP_VERSION

try:
    import mss
    import pygetwindow
    import pytesseract
    from PIL import Image, ImageTk
except ImportError as exc:
    raise SystemExit(
        "Thiếu thư viện. Hãy cài dependencies bằng: python -m pip install -r requirements.txt"
    ) from exc


POLL_INTERVAL_SECONDS = 2
LIVE_GUIDANCE_INTERVAL_SECONDS = 0.6


class BibiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bibi - BlueStacks Monitor")
        self.root.geometry("940x850")
        self.root.minsize(760, 700)
        if sys.platform == "win32":
            self.root.state("zoomed")
            self.root.bind("<Escape>", lambda _event: self.root.state("normal"))
        else:
            self.root.attributes("-fullscreen", True)
            self.root.bind(
                "<Escape>",
                lambda _event: self.root.attributes("-fullscreen", False),
            )

        self.running = False
        self.live_guidance = False
        self.live_cache: tuple[tuple[str, ...], ...] | None = None
        self.worker: threading.Thread | None = None
        self.automation_thread: threading.Thread | None = None
        self.update_thread: threading.Thread | None = None
        self.automation_stop = threading.Event()
        self.update_stop = threading.Event()
        self.solution_moves: list[Move] | None = None
        self.solution_tubes: tuple[tuple[str, ...], ...] | None = None
        self.auto_expected_tubes: tuple[tuple[str, ...], ...] | None = None
        self.auto_expected_positions: tuple[tuple[int, int], ...] | None = None
        self.auto_expected_window: str | None = None
        self.auto_play_pending = False
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.window_map: dict[str, object] = {}
        self.preview_image: ImageTk.PhotoImage | None = None
        self.last_count: int | None = None
        self.coin_count = tk.StringVar(value="Chưa nhận diện")
        self.coin_delta = tk.StringVar(value="Chênh lệch: --")
        self.status = tk.StringVar(value="Đang dừng")
        self.update_status = tk.StringVar(value="")
        self.window_choice = tk.StringVar()
        self.roi_x = tk.StringVar(value="0")
        self.roi_y = tk.StringVar(value="0")
        self.roi_w = tk.StringVar(value="0")
        self.roi_h = tk.StringVar(value="0")

        self._build_ui()
        self.refresh_windows()
        self.root.after(150, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        if getattr(sys, "frozen", False):
            self.root.after(1000, self.check_for_updates)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        monitor = ttk.LabelFrame(container, text="Theo dõi BlueStacks", padding=10)
        monitor.pack(fill="x")
        ttk.Label(monitor, text="Cửa sổ:").grid(row=0, column=0, sticky="w")
        self.window_combo = ttk.Combobox(
            monitor, textvariable=self.window_choice, state="readonly", width=48
        )
        self.window_combo.grid(row=0, column=1, padx=6, sticky="ew")
        ttk.Button(monitor, text="Làm mới", command=self.refresh_windows).grid(row=0, column=2)
        self.start_button = ttk.Button(monitor, text="Bắt đầu", command=self.start_monitoring)
        self.start_button.grid(row=0, column=3, padx=(8, 0))
        self.stop_button = ttk.Button(
            monitor, text="Dừng", command=self.stop_monitoring, state="disabled"
        )
        self.stop_button.grid(row=0, column=4, padx=(6, 0))
        self.live_guidance_button = ttk.Button(
            monitor,
            text="Tự xem & chỉ dẫn",
            command=self.start_live_guidance,
        )
        self.live_guidance_button.grid(row=0, column=5, padx=(6, 0))
        self.update_button = ttk.Button(
            monitor, text="Kiểm tra cập nhật", command=self.check_for_updates
        )
        self.update_button.grid(row=0, column=6, padx=(6, 0))
        ttk.Button(
            monitor, text="Tải setup", command=self.open_setup_download
        ).grid(row=0, column=7, padx=(6, 0))
        ttk.Label(monitor, textvariable=self.status).grid(
            row=1, column=0, columnspan=8, sticky="w", pady=(8, 0)
        )
        ttk.Label(monitor, textvariable=self.update_status).grid(
            row=2, column=0, columnspan=8, sticky="w", pady=(4, 0)
        )
        monitor.columnconfigure(1, weight=1)

        roi = ttk.LabelFrame(container, text="Vùng đọc số (tọa độ tương đối trong cửa sổ)", padding=10)
        roi.pack(fill="x", pady=(10, 0))
        ttk.Label(roi, text="X").grid(row=0, column=0)
        ttk.Entry(roi, textvariable=self.roi_x, width=7).grid(row=0, column=1, padx=(3, 10))
        ttk.Label(roi, text="Y").grid(row=0, column=2)
        ttk.Entry(roi, textvariable=self.roi_y, width=7).grid(row=0, column=3, padx=(3, 10))
        ttk.Label(roi, text="Rộng").grid(row=0, column=4)
        ttk.Entry(roi, textvariable=self.roi_w, width=7).grid(row=0, column=5, padx=(3, 10))
        ttk.Label(roi, text="Cao").grid(row=0, column=6)
        ttk.Entry(roi, textvariable=self.roi_h, width=7).grid(row=0, column=7, padx=(3, 10))
        ttk.Label(roi, text="Để rộng/cao = 0 để đọc toàn cửa sổ.").grid(
            row=0, column=8, sticky="w"
        )
        roi.columnconfigure(8, weight=1)

        count_panel = ttk.LabelFrame(container, text="Số đọc được bằng OCR", padding=10)
        count_panel.pack(fill="x", pady=(10, 0))
        ttk.Label(count_panel, textvariable=self.coin_count, font=("Segoe UI", 18, "bold")).pack(
            side="left"
        )
        ttk.Label(count_panel, textvariable=self.coin_delta).pack(side="right")

        preview_panel = ttk.LabelFrame(container, text="Ảnh chụp BlueStacks", padding=8)
        preview_panel.pack(fill="both", expand=True, pady=(10, 0))
        self.preview = ttk.Label(preview_panel, text="Nhấn Bắt đầu để theo dõi màn hình.")
        self.preview.pack(expand=True)

        solver = ttk.LabelFrame(container, text="Water Sort (nhập từ đáy ống lên miệng ống)", padding=10)
        solver.pack(fill="x", pady=(10, 0))
        ttk.Label(
            solver,
            text="Mỗi dòng là một ống; dùng một ký tự cho mỗi màu, ví dụ RBG. Dùng dấu - cho ống trống.",
        ).pack(anchor="w")
        self.tubes_input = tk.Text(solver, height=5, wrap="none")
        self.tubes_input.pack(fill="x", pady=(5, 6))
        self.tubes_input.insert("1.0", "RRGG\nGGRR\n-\n-")
        self.solve_button = ttk.Button(solver, text="Tìm lời giải", command=self.solve)
        self.solve_button.pack(anchor="w")
        self.auto_solve_button = ttk.Button(
            solver,
            text="Tự nhận diện & tính",
            command=self.auto_solve_screen,
        )
        self.auto_solve_button.pack(anchor="w", pady=(5, 0))
        ttk.Label(
            solver,
            text=(
                "Tọa độ tâm ống theo từng hàng từ trên xuống, trái sang phải; "
                "tương đối trong cửa sổ BlueStacks (x,y; x,y; ...):"
            ),
        ).pack(anchor="w", pady=(8, 2))
        self.positions_input = ttk.Entry(solver)
        self.positions_input.pack(fill="x")
        controls = ttk.Frame(solver)
        controls.pack(anchor="w", pady=(6, 0))
        self.execute_button = ttk.Button(
            controls, text="Tự bấm lời giải", command=self.execute_solution, state="disabled"
        )
        self.execute_button.pack(side="left")
        self.stop_automation_button = ttk.Button(
            controls, text="Dừng tự bấm", command=self.stop_automation, state="disabled"
        )
        self.stop_automation_button.pack(side="left", padx=(6, 0))
        self.solution = tk.Text(solver, height=5, wrap="word", state="disabled")
        self.solution.pack(fill="x", pady=(6, 0))

    def refresh_windows(self) -> None:
        try:
            windows = pygetwindow.getAllWindows()
        except Exception as exc:
            self.status.set(f"Không thể liệt kê cửa sổ: {exc}")
            return

        self.window_map = {
            f"{window.title} ({window.width}x{window.height})": window
            for window in windows
            if window.title and "bluestacks" in window.title.lower()
            and window.width > 0 and window.height > 0
        }
        values = list(self.window_map)
        self.window_combo["values"] = values
        if values and self.window_choice.get() not in self.window_map:
            self.window_choice.set(values[0])
        elif not values:
            self.window_choice.set("")
            self.status.set("Không tìm thấy cửa sổ BlueStacks. Hãy mở BlueStacks rồi làm mới.")

    def start_monitoring(self) -> None:
        selected = self.window_map.get(self.window_choice.get())
        if selected is None:
            messagebox.showwarning("Bibi", "Hãy chọn cửa sổ BlueStacks trước.")
            return
        if self.running:
            return
        self.live_guidance = False
        self.live_cache = None
        try:
            region = self._region(selected)
        except ValueError as exc:
            messagebox.showerror("Vùng đọc không hợp lệ", str(exc))
            return
        self.running = True
        self.start_button.configure(state="disabled")
        self.live_guidance_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Đang theo dõi — Bibi không tự bấm.")
        self.worker = threading.Thread(
            target=self._monitor_loop, args=(selected, region), daemon=True
        )
        self.worker.start()

    def stop_monitoring(self) -> None:
        self.live_guidance = False
        self.live_cache = None
        self.running = False
        if self.worker and self.worker.is_alive():
            self.start_button.configure(state="disabled")
            self.live_guidance_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")
            self.status.set("Đang dừng...")
        else:
            self.start_button.configure(state="normal")
            self.live_guidance_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status.set("Đang dừng")

    def start_live_guidance(self) -> None:
        if self.running:
            return
        self.running = True
        self.live_guidance = True
        self.live_cache = None
        self.start_button.configure(state="disabled")
        self.live_guidance_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Đang xem toàn màn hình — đang nhận diện chỉ dẫn...")
        self.worker = threading.Thread(
            target=self._live_guidance_loop,
            daemon=True,
        )
        self.worker.start()

    def _live_guidance_loop(self) -> None:
        last_error = ""
        try:
            with mss.mss() as screen:
                while self.running and self.live_guidance:
                    monitor = screen.monitors[1]
                    screenshot = Image.frombytes(
                        "RGB",
                        (monitor["width"], monitor["height"]),
                        screen.grab(monitor).rgb,
                    )
                    try:
                        tubes, positions = detect_water_sort_board(screenshot)
                        if tubes != self.live_cache:
                            moves = solve_water_sort(tubes)
                            self.live_cache = tubes
                            self.events.put(
                                ("live_guidance", (screenshot, tubes, positions, moves))
                            )
                        last_error = ""
                    except (BoardDetectionError, ValueError) as exc:
                        if str(exc) != last_error:
                            last_error = str(exc)
                            self.events.put(("guidance_error", str(exc)))
                    except Exception as exc:
                        if str(exc) != last_error:
                            last_error = f"Lỗi xem màn hình: {exc}"
                            self.events.put(("guidance_error", last_error))
                    time.sleep(LIVE_GUIDANCE_INTERVAL_SECONDS)
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.events.put(("stopped", None))

    def _region(self, window: object) -> tuple[int, int, int, int]:
        try:
            x, y, width, height = (int(value.get()) for value in (self.roi_x, self.roi_y, self.roi_w, self.roi_h))
        except ValueError as exc:
            raise ValueError("Tọa độ vùng đọc phải là số nguyên không âm.") from exc
        if min(x, y, width, height) < 0:
            raise ValueError("Tọa độ vùng đọc không được âm.")
        if width == 0:
            width = window.width - x
        if height == 0:
            height = window.height - y
        if x >= window.width or y >= window.height or width <= 0 or height <= 0:
            raise ValueError("Vùng đọc nằm ngoài cửa sổ BlueStacks.")
        return x, y, min(width, window.width - x), min(height, window.height - y)

    def _capture_window(self, window: object) -> Image.Image:
        if window.width <= 0 or window.height <= 0:
            raise RuntimeError("Cửa sổ BlueStacks đã đóng hoặc bị thu nhỏ.")
        bounds = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height,
        }
        with mss.mss() as screen:
            capture = screen.grab(bounds)
        return Image.frombytes("RGB", (window.width, window.height), capture.rgb)

    def _monitor_loop(self, window: object, region: tuple[int, int, int, int]) -> None:
        try:
            with mss.mss() as screen:
                while self.running:
                    if window.width <= 0 or window.height <= 0:
                        self.events.put(("status", "Cửa sổ BlueStacks đã đóng hoặc bị thu nhỏ."))
                        break
                    x, y, width, height = region
                    bounds = {
                        "left": window.left,
                        "top": window.top,
                        "width": window.width,
                        "height": window.height,
                    }
                    screenshot = Image.frombytes(
                        "RGB",
                        (window.width, window.height),
                        screen.grab(bounds).rgb,
                    )
                    crop = screenshot.crop((x, y, x + width, y + height))
                    text = pytesseract.image_to_string(crop, config="--psm 6 -c tessedit_char_whitelist=0123456789,.")
                    numbers = re.findall(r"\d[\d,.]*", text)
                    self.events.put(("frame", (screenshot, numbers, text.strip())))
                    time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exc:
            self.events.put(("error", str(exc)))
        finally:
            self.events.put(("stopped", None))

    def _process_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "frame":
                    screenshot, numbers, recognized = payload
                    self._show_frame(screenshot)
                    if numbers:
                        digits = re.sub(r"\D", "", numbers[0])
                        if digits:
                            count = int(digits)
                            delta = "--" if self.last_count is None else f"{count - self.last_count:+,}"
                            self.coin_count.set(f"Nhận diện: {count:,}")
                            self.coin_delta.set(f"Chênh lệch: {delta}")
                            self.last_count = count
                    else:
                        self.coin_count.set("Không thấy số trong vùng đã chọn")
                    self.status.set("Đang theo dõi — OCR: " + (recognized[:70] or "không đọc được chữ"))
                elif kind == "live_guidance":
                    screenshot, tubes, positions, moves = payload
                    if moves:
                        first_move = moves[0]
                        annotated = annotate_water_sort_guidance(
                            screenshot,
                            positions,
                            first_move,
                        )
                        self._show_frame(annotated)
                        lines = [
                            f"{i}. Đổ {move.color} x{move.amount}: ống {move.source} -> ống {move.target}"
                            for i, move in enumerate(moves, start=1)
                        ]
                        self._set_solution("\n".join(lines))
                        self.status.set(
                            f"Lượt kế tiếp: màu {first_move.color} "
                            f"từ ống {first_move.source} sang ống {first_move.target} "
                            f"(đỏ -> xanh lá)"
                        )
                    elif moves == []:
                        self._show_frame(screenshot)
                        self._set_solution("Bàn chơi đã được giải.")
                        self.status.set("Đã giải — không cần lượt đổ.")
                    else:
                        self._show_frame(screenshot)
                        self._set_solution("Không tìm được lời giải trong giới hạn tìm kiếm.")
                        self.status.set("Không tìm được lời giải.")
                    tube_text = "\n".join("".join(tube) or "-" for tube in tubes)
                    self.tubes_input.delete("1.0", "end")
                    self.tubes_input.insert("1.0", tube_text)
                    self.positions_input.delete(0, "end")
                    self.positions_input.insert(
                        0,
                        "; ".join(f"{x},{y}" for x, y in positions),
                    )
                elif kind == "guidance_error":
                    self.status.set(f"Chỉ dẫn đang chờ: {payload}")
                elif kind == "error":
                    self.status.set(f"Lỗi theo dõi: {payload}")
                elif kind == "status":
                    self.status.set(str(payload))
                elif kind == "update_progress":
                    self.update_status.set(str(payload))
                elif kind == "update_result":
                    result, details = payload
                    self.update_thread = None
                    self.update_button.configure(state="normal")
                    if result == "current":
                        self.update_status.set(f"Bibi đang ở phiên bản mới nhất ({APP_VERSION}).")
                    elif result == "cancelled":
                        self.update_status.set("Đã hủy kiểm tra/tải bản cập nhật.")
                    else:
                        self.update_status.set(f"Lỗi cập nhật: {details}")
                elif kind == "update_ready":
                    update, installer_path = payload
                    self.update_thread = None
                    try:
                        launch_installer(installer_path)
                    except Exception as exc:
                        self.update_button.configure(state="normal")
                        self.update_status.set(f"Không thể khởi chạy bộ cài: {exc}")
                    else:
                        self.update_status.set(
                            f"Đang cài Bibi {update.version}; ứng dụng sẽ khởi động lại."
                        )
                        self.root.after(500, self.close)
                elif kind == "auto_detected":
                    window_key, screenshot, tube_text, position_text = payload
                    self._show_frame(screenshot)
                    try:
                        selected = self.window_map.get(window_key)
                        if selected is None or self.window_choice.get() != window_key:
                            raise ValueError(
                                "Cửa sổ BlueStacks đã thay đổi; hãy quét lại bàn chơi."
                            )
                        tubes = parse_tubes(tube_text)
                        parse_tube_positions(
                            position_text,
                            len(tubes),
                            selected.width,
                            selected.height,
                        )
                    except (KeyError, ValueError) as exc:
                        self.solve_button.configure(state="normal")
                        self.auto_solve_button.configure(state="normal")
                        self.execute_button.configure(
                            state="normal" if self.solution_moves else "disabled"
                        )
                        self.auto_play_pending = False
                        self.auto_expected_tubes = None
                        self.auto_expected_positions = None
                        self.auto_expected_window = None
                        self.status.set(f"Không thể dùng kết quả nhận diện: {exc}")
                        messagebox.showerror("Nhận diện Water Sort", str(exc))
                        continue

                    self.tubes_input.delete("1.0", "end")
                    self.tubes_input.insert("1.0", tube_text)
                    self.positions_input.delete(0, "end")
                    self.positions_input.insert(0, position_text)
                    self.auto_expected_tubes = tubes
                    self.auto_expected_positions = parse_tube_positions(
                        position_text,
                        len(tubes),
                        selected.width,
                        selected.height,
                    )
                    self.auto_expected_window = window_key
                    self.auto_play_pending = True
                    self.status.set(
                        f"Nhận diện được {len(tubes)} ống; đang tính lời giải..."
                    )
                    self.solve()
                elif kind == "auto_detection_error":
                    self.solve_button.configure(state="normal")
                    self.auto_solve_button.configure(state="normal")
                    self.execute_button.configure(
                        state="normal" if self.solution_moves else "disabled"
                    )
                    self.auto_play_pending = False
                    self.auto_expected_tubes = None
                    self.auto_expected_positions = None
                    self.auto_expected_window = None
                    self.status.set(f"Không thể tự nhận diện: {payload}")
                    messagebox.showerror("Không thể nhận diện Water Sort", str(payload))
                elif kind == "solution":
                    self.solve_button.configure(state="normal")
                    self.auto_solve_button.configure(state="normal")
                    if payload is None:
                        self.auto_play_pending = False
                        self.auto_expected_tubes = None
                        self.auto_expected_positions = None
                        self.auto_expected_window = None
                        self.solution_moves = None
                        self.solution_tubes = None
                        self.execute_button.configure(state="disabled")
                        self._set_solution(
                            f"Chưa tìm được lời giải trong giới hạn {MAX_SEARCH_STATES:,} trạng thái."
                        )
                    elif not payload:
                        self.auto_play_pending = False
                        self.auto_expected_tubes = None
                        self.auto_expected_positions = None
                        self.auto_expected_window = None
                        self.solution_moves = []
                        self.solution_tubes = None
                        self.execute_button.configure(state="disabled")
                        self._set_solution("Trạng thái này đã được giải.")
                    else:
                        self.solution_moves = payload
                        lines = [
                            f"{i}. Đổ {move.color} x{move.amount}: ống {move.source} → ống {move.target}"
                            for i, move in enumerate(payload, start=1)
                        ]
                        self.execute_button.configure(state="normal")
                        self._set_solution("\n".join(lines))
                        if self.auto_play_pending:
                            self.auto_play_pending = False
                            state_text = "\n".join(
                                f"{index}: {''.join(tube) or '-'}"
                                for index, tube in enumerate(self.solution_tubes or (), start=1)
                            )
                            confirmed = messagebox.askyesno(
                                "Xác nhận trạng thái nhận diện",
                                (
                                    f"Đã nhận diện {len(self.solution_tubes or ())} ống:\n"
                                    f"{state_text}\n\n"
                                    "Mỗi chữ cái đại diện cho một màu. "
                                    f"Lời giải có {len(payload)} lượt đổ. "
                                    "Nếu trạng thái đúng, chọn Có để Bibi tự bấm."
                                ),
                            )
                            if confirmed:
                                self.execute_solution(confirmed=True)
                            else:
                                self.auto_expected_tubes = None
                                self.auto_expected_positions = None
                                self.auto_expected_window = None
                                self.status.set("Đã hủy tự bấm; lời giải vẫn được giữ lại.")
                elif kind == "automation_finished":
                    completed, error = payload
                    self.automation_thread = None
                    self.solve_button.configure(state="normal")
                    self.auto_solve_button.configure(state="normal")
                    self.execute_button.configure(
                        state="normal" if self.solution_moves else "disabled"
                    )
                    self.stop_automation_button.configure(state="disabled")
                    if error:
                        self.status.set(f"Lỗi tự bấm: {error}")
                    elif completed:
                        self.status.set("Đã bấm xong lời giải.")
                    else:
                        self.status.set("Đã dừng tự bấm.")
                    self.auto_expected_tubes = None
                    self.auto_expected_positions = None
                    self.auto_expected_window = None
                elif kind == "solver_error":
                    self.solve_button.configure(state="normal")
                    self.auto_solve_button.configure(state="normal")
                    self.auto_play_pending = False
                    self.auto_expected_tubes = None
                    self.auto_expected_positions = None
                    self.auto_expected_window = None
                    self._set_solution(f"Lỗi khi giải: {payload}")
                elif kind == "stopped":
                    self.worker = None
                    self.stop_monitoring()
        except queue.Empty:
            pass
        self.root.after(150, self._process_events)

    def _show_frame(self, image: Image.Image) -> None:
        image.thumbnail((1500, 700))
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.preview_image, text="")

    def solve(self) -> None:
        if not self.auto_play_pending:
            self.auto_expected_tubes = None
            self.auto_expected_positions = None
            self.auto_expected_window = None
        try:
            tubes = parse_tubes(self.tubes_input.get("1.0", "end"))
        except ValueError as exc:
            messagebox.showerror("Trạng thái Water Sort không hợp lệ", str(exc))
            return

        self.solve_button.configure(state="disabled")
        self.auto_solve_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.solution_moves = None
        self.solution_tubes = tubes
        self._set_solution("Đang tìm lời giải...")

        def run_solver() -> None:
            try:
                result = solve_water_sort(tubes)
                self.events.put(("solution", result))
            except Exception as exc:
                self.events.put(("solver_error", str(exc)))

        threading.Thread(target=run_solver, daemon=True).start()

    def auto_solve_screen(self) -> None:
        selected = self.window_map.get(self.window_choice.get())
        if selected is None:
            messagebox.showwarning("Bibi", "Hãy chọn cửa sổ BlueStacks trước.")
            return
        selected_key = self.window_choice.get()
        if self.auto_play_pending or (
            self.automation_thread and self.automation_thread.is_alive()
        ):
            return

        self.auto_solve_button.configure(state="disabled")
        self.solve_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.status.set("Đang chụp màn hình và nhận diện các ống...")

        def detect_board() -> None:
            try:
                screenshot = self._capture_window(selected)
                tubes, positions = detect_water_sort_board(screenshot)
                tube_text = "\n".join("".join(tube) or "-" for tube in tubes)
                position_text = "; ".join(f"{x},{y}" for x, y in positions)
                parse_tubes(tube_text)
                self.events.put(
                    (
                        "auto_detected",
                        (selected_key, screenshot, tube_text, position_text),
                    )
                )
            except (BoardDetectionError, ValueError, RuntimeError) as exc:
                self.events.put(("auto_detection_error", str(exc)))
            except Exception as exc:
                self.events.put(("auto_detection_error", f"Lỗi chụp/đọc màn hình: {exc}"))

        threading.Thread(target=detect_board, daemon=True).start()

    def check_for_updates(self) -> None:
        if not getattr(sys, "frozen", False):
            self.update_status.set("Tự cập nhật chỉ khả dụng trong bản cài Windows.")
            return
        if self.update_thread and self.update_thread.is_alive():
            return

        self.update_stop.clear()
        self.update_button.configure(state="disabled")
        self.update_status.set("Đang kiểm tra bản cập nhật...")

        def check_and_download() -> None:
            try:
                update = check_latest_update(APP_VERSION)
                if update is None:
                    self.events.put(("update_result", ("current", None)))
                    return
                self.events.put(
                    ("update_progress", f"Tìm thấy Bibi {update.version}; đang tải bộ cài...")
                )
                installer_path = (
                    Path(tempfile.gettempdir())
                    / "Bibi"
                    / "updates"
                    / update.version
                    / "Bibi-Setup.exe"
                )
                download_update(update, installer_path, self.update_stop)
                if self.update_stop.is_set():
                    self.events.put(("update_result", ("cancelled", None)))
                    return
                self.events.put(("update_ready", (update, installer_path)))
            except InterruptedError:
                self.events.put(("update_result", ("cancelled", None)))
            except Exception as exc:
                self.events.put(("update_result", ("error", str(exc))))

        self.update_thread = threading.Thread(target=check_and_download, daemon=True)
        self.update_thread.start()

    def open_setup_download(self) -> None:
        try:
            opened = webbrowser.open(INSTALLER_DOWNLOAD_URL, new=2)
        except (OSError, webbrowser.Error) as exc:
            messagebox.showerror("Không thể tải setup", f"Không thể mở liên kết tải setup: {exc}")
            return
        if not opened:
            messagebox.showerror("Không thể tải setup", "Không thể mở trình duyệt để tải bộ cài.")

    def execute_solution(self, confirmed: bool = False) -> None:
        if (
            not self.solution_moves
            or self.automation_thread
            and self.automation_thread.is_alive()
        ):
            return

        selected = self.window_map.get(self.window_choice.get())
        if selected is None:
            messagebox.showwarning("Bibi", "Hãy chọn cửa sổ BlueStacks trước.")
            return
        if (
            self.auto_expected_tubes is not None
            and self.window_choice.get() != self.auto_expected_window
        ):
            messagebox.showerror(
                "Không thể tự bấm",
                "Cửa sổ BlueStacks đã thay đổi sau khi nhận diện; hãy quét lại bàn chơi.",
            )
            return
        if selected.width <= 0 or selected.height <= 0:
            messagebox.showerror("Bibi", "Cửa sổ BlueStacks đang bị thu nhỏ hoặc không khả dụng.")
            return
        try:
            current_tubes = parse_tubes(self.tubes_input.get("1.0", "end"))
            if current_tubes != self.solution_tubes:
                raise ValueError("Trạng thái ống đã thay đổi. Hãy tìm lời giải lại trước.")
            positions = parse_tube_positions(
                self.positions_input.get(),
                len(current_tubes),
                selected.width,
                selected.height,
            )
        except ValueError as exc:
            messagebox.showerror("Không thể tự bấm", str(exc))
            return

        if not confirmed and not messagebox.askyesno(
            "Xác nhận tự bấm",
            f"Bibi sẽ thực hiện {len(self.solution_moves)} lượt đổ trên BlueStacks. Tiếp tục?",
        ):
            return

        expected_tubes = self.auto_expected_tubes
        expected_positions = self.auto_expected_positions
        self.automation_stop.clear()
        self.solve_button.configure(state="disabled")
        self.auto_solve_button.configure(state="disabled")
        self.execute_button.configure(state="disabled")
        self.stop_automation_button.configure(state="normal")
        self.status.set("Đang tự bấm lời giải...")

        def run_automation() -> None:
            error = None
            completed = False
            try:
                import pyautogui

                pyautogui.FAILSAFE = True
                selected.activate()
                time.sleep(0.3)
                if expected_tubes is not None:
                    current_image = self._capture_window(selected)
                    current_tubes, current_positions = detect_water_sort_board(current_image)
                    if current_tubes != expected_tubes:
                        raise RuntimeError(
                            "Bàn chơi đã đổi sau khi nhận diện; hãy quét lại trước khi bấm."
                        )
                    if (
                        expected_positions is None
                        or len(current_positions) != len(expected_positions)
                        or any(
                            abs(current[0] - expected[0]) > 8
                            or abs(current[1] - expected[1]) > 8
                            for current, expected in zip(current_positions, expected_positions)
                        )
                    ):
                        raise RuntimeError(
                            "Vị trí ống đã đổi sau khi nhận diện; hãy quét lại trước khi bấm."
                        )

                def click_tube(tube_number: int) -> None:
                    if selected.width <= 0 or selected.height <= 0:
                        raise RuntimeError("Cửa sổ BlueStacks đã đóng hoặc bị thu nhỏ.")
                    x, y = positions[tube_number - 1]
                    if x >= selected.width or y >= selected.height:
                        raise RuntimeError("Kích thước cửa sổ đã đổi; hãy cập nhật tọa độ ống.")
                    pyautogui.click(selected.left + x, selected.top + y)

                completed = execute_moves(
                    self.solution_moves or [],
                    click_tube,
                    self.automation_stop,
                )
            except Exception as exc:
                error = str(exc)
            finally:
                self.events.put(("automation_finished", (completed, error)))

        self.automation_thread = threading.Thread(target=run_automation, daemon=True)
        self.automation_thread.start()

    def stop_automation(self) -> None:
        self.automation_stop.set()
        self.stop_automation_button.configure(state="disabled")
        self.status.set("Đang yêu cầu dừng tự bấm...")

    def _set_solution(self, text: str) -> None:
        self.solution.configure(state="normal")
        self.solution.delete("1.0", "end")
        self.solution.insert("1.0", text)
        self.solution.configure(state="disabled")

    def close(self) -> None:
        self.running = False
        self.automation_stop.set()
        self.update_stop.set()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    BibiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
