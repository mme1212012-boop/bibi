from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from water_sort import MAX_SEARCH_STATES, parse_tubes, solve_water_sort

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


class BibiApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bibi - BlueStacks Monitor")
        self.root.geometry("940x760")
        self.root.minsize(760, 600)

        self.running = False
        self.worker: threading.Thread | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.window_map: dict[str, object] = {}
        self.preview_image: ImageTk.PhotoImage | None = None
        self.last_count: int | None = None
        self.coin_count = tk.StringVar(value="Chưa nhận diện")
        self.coin_delta = tk.StringVar(value="Chênh lệch: --")
        self.status = tk.StringVar(value="Đang dừng")
        self.window_choice = tk.StringVar()
        self.roi_x = tk.StringVar(value="0")
        self.roi_y = tk.StringVar(value="0")
        self.roi_w = tk.StringVar(value="0")
        self.roi_h = tk.StringVar(value="0")

        self._build_ui()
        self.refresh_windows()
        self.root.after(150, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

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
        ttk.Label(monitor, textvariable=self.status).grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(8, 0)
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

        solver = ttk.LabelFrame(
            container, text="Gợi ý Water Sort (nhập từ đáy ống lên miệng ống)", padding=10
        )
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
        try:
            region = self._region(selected)
        except ValueError as exc:
            messagebox.showerror("Vùng đọc không hợp lệ", str(exc))
            return
        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set("Đang theo dõi — Bibi không tự bấm.")
        self.worker = threading.Thread(
            target=self._monitor_loop, args=(selected, region), daemon=True
        )
        self.worker.start()

    def stop_monitoring(self) -> None:
        self.running = False
        if self.worker and self.worker.is_alive():
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")
            self.status.set("Đang dừng...")
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status.set("Đang dừng")

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
                elif kind == "error":
                    self.status.set(f"Lỗi theo dõi: {payload}")
                elif kind == "status":
                    self.status.set(str(payload))
                elif kind == "solution":
                    self.solve_button.configure(state="normal")
                    if payload is None:
                        self._set_solution(
                            f"Chưa tìm được lời giải trong giới hạn {MAX_SEARCH_STATES:,} trạng thái."
                        )
                    elif not payload:
                        self._set_solution("Trạng thái này đã được giải.")
                    else:
                        lines = [
                            f"{i}. Đổ {move.color} x{move.amount}: ống {move.source} → ống {move.target}"
                            for i, move in enumerate(payload, start=1)
                        ]
                        self._set_solution("\n".join(lines))
                elif kind == "solver_error":
                    self.solve_button.configure(state="normal")
                    self._set_solution(f"Lỗi khi giải: {payload}")
                elif kind == "stopped":
                    self.worker = None
                    self.stop_monitoring()
        except queue.Empty:
            pass
        self.root.after(150, self._process_events)

    def _show_frame(self, image: Image.Image) -> None:
        image.thumbnail((780, 330))
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.preview_image, text="")

    def solve(self) -> None:
        try:
            tubes = parse_tubes(self.tubes_input.get("1.0", "end"))
        except ValueError as exc:
            messagebox.showerror("Trạng thái Water Sort không hợp lệ", str(exc))
            return

        self.solve_button.configure(state="disabled")
        self._set_solution("Đang tìm lời giải...")

        def run_solver() -> None:
            try:
                result = solve_water_sort(tubes)
                self.events.put(("solution", result))
            except Exception as exc:
                self.events.put(("solver_error", str(exc)))

        threading.Thread(target=run_solver, daemon=True).start()

    def _set_solution(self, text: str) -> None:
        self.solution.configure(state="normal")
        self.solution.delete("1.0", "end")
        self.solution.insert("1.0", text)
        self.solution.configure(state="disabled")

    def close(self) -> None:
        self.running = False
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    BibiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
