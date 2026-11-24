from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from water_sort import Move


def parse_tube_positions(
    text: str,
    tube_count: int,
    window_width: int,
    window_height: int,
) -> tuple[tuple[int, int], ...]:
    entries = text.split(";")
    if len(entries) != tube_count:
        raise ValueError(
            f"Hãy nhập tọa độ cho đủ {tube_count} ống theo thứ tự từng hàng từ trên xuống."
        )

    positions = []
    for tube_number, entry in enumerate(entries, start=1):
        coordinates = entry.strip().split(",")
        if len(coordinates) != 2:
            raise ValueError(f"Tọa độ ống {tube_number} phải có dạng x,y.")
        try:
            x, y = (int(value.strip()) for value in coordinates)
        except ValueError as exc:
            raise ValueError(f"Tọa độ ống {tube_number} phải là số nguyên.") from exc
        if not (0 <= x < window_width and 0 <= y < window_height):
            raise ValueError(f"Tọa độ ống {tube_number} nằm ngoài cửa sổ BlueStacks.")
        positions.append((x, y))

    return tuple(positions)


def execute_moves(
    moves: Sequence[Move],
    click_tube: Callable[[int], None],
    stop_event: threading.Event,
    delay_seconds: float = 0.35,
) -> bool:
    for move in moves:
        if stop_event.is_set():
            return False
        click_tube(move.source)
        if stop_event.wait(delay_seconds):
            return False
        click_tube(move.target)
        if stop_event.wait(delay_seconds):
            return False
    return not stop_event.is_set()
