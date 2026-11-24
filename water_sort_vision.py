from __future__ import annotations

import colorsys
import math
from typing import Protocol


class RGBImage(Protocol):
    size: tuple[int, int]

    def getpixel(self, xy: tuple[int, int]) -> tuple[int, int, int]: ...


class BoardDetectionError(ValueError):
    pass


def _is_background(color: tuple[int, int, int]) -> bool:
    red, green, blue = color
    return (
        red >= 120
        and blue >= red + 24
        and blue >= green + 18
        and (max(color) - min(color)) / max(color) < 0.48
    )


def _game_bounds(image: RGBImage, scale: int) -> tuple[int, int, int, int]:
    width = math.ceil(image.size[0] / scale)
    height = math.ceil(image.size[1] / scale)
    column_counts = [0] * width
    for y in range(height):
        source_y = min(y * scale, image.size[1] - 1)
        for x in range(width):
            source_x = min(x * scale, image.size[0] - 1)
            if _is_background(image.getpixel((source_x, source_y))):
                column_counts[x] += 1

    threshold = max(12, int(height * 0.16))
    runs = []
    start = None
    for x, count in enumerate(column_counts + [0]):
        if count >= threshold and start is None:
            start = x
        elif count < threshold and start is not None:
            runs.append((start, x))
            start = None
    if not runs:
        raise BoardDetectionError("Không tìm thấy vùng chơi nền xanh nhạt trong ảnh.")
    x0, x1 = max(runs, key=lambda run: run[1] - run[0])
    if x1 - x0 < width * 0.15:
        raise BoardDetectionError("Không tìm thấy vùng chơi đủ rộng.")

    row_threshold = max(4, int((x1 - x0) * 0.16))
    y_rows = []
    for y in range(height):
        count = sum(
            _is_background(
                image.getpixel((min(x * scale, image.size[0] - 1), min(y * scale, image.size[1] - 1)))
            )
            for x in range(x0, x1)
        )
        if count >= row_threshold:
            y_rows.append(y)
    if not y_rows:
        raise BoardDetectionError("Không thể xác định chiều cao vùng chơi.")
    return x0, y_rows[0], x1, y_rows[-1] + 1


def _integral_mask(
    image: RGBImage,
    bounds: tuple[int, int, int, int],
    scale: int,
) -> tuple[list[list[int]], int, int]:
    x0, y0, x1, y1 = bounds
    width, height = x1 - x0, y1 - y0
    integral = [[0] * (width + 1) for _ in range(height + 1)]
    for y in range(height):
        row_sum = 0
        source_y = min((y0 + y) * scale, image.size[1] - 1)
        for x in range(width):
            source_x = min((x0 + x) * scale, image.size[0] - 1)
            color = image.getpixel((source_x, source_y))
            row_sum += int(min(color) >= 235)
            integral[y + 1][x + 1] = integral[y][x + 1] + row_sum
    return integral, width, height


def _window_sum(
    integral: list[list[int]],
    x: int,
    y: int,
    width: int,
    height: int,
) -> int:
    return (
        integral[y + height][x + width]
        - integral[y][x + width]
        - integral[y + height][x]
        + integral[y][x]
    )


def _rim_score(
    image: RGBImage,
    bounds: tuple[int, int, int, int],
    scale: int,
    center_x: int,
    center_y: int,
    width: int,
    height: int,
) -> float:
    x0, y0, _, _ = bounds
    expected = 0
    matched = 0
    for dy in range(-height // 2, height // 2 + 1):
        for dx in range(-width // 2, width // 2 + 1):
            radius = math.sqrt(
                (dx / (width * 0.44)) ** 2 + (dy / (height * 0.42)) ** 2
            )
            if not 0.72 <= radius <= 1.18:
                continue
            expected += 1
            source_x = min(max((x0 + center_x + dx) * scale, 0), image.size[0] - 1)
            source_y = min(max((y0 + center_y + dy) * scale, 0), image.size[1] - 1)
            if min(image.getpixel((source_x, source_y))) >= 235:
                matched += 1
    return matched / expected if expected else 0


def _find_tube_mouths(
    image: RGBImage,
    bounds: tuple[int, int, int, int],
    scale: int,
) -> tuple[tuple[int, int, int], ...]:
    x0, y0, _, _ = bounds
    integral, width, height = _integral_mask(image, bounds, scale)
    window_width = max(8, round(width * 0.085))
    window_height = max(6, round(window_width * 0.62))
    step = max(1, window_width // 5)
    minimum_score = max(12, round(window_width * window_height * 0.08))
    search_start = int(height * (0.27 if height > width * 1.3 else 0.08))
    search_end = int(height * 0.84) - window_height
    candidates = []
    for y in range(search_start, max(search_start, search_end), step):
        for x in range(0, width - window_width + 1, step):
            score = _window_sum(integral, x, y, window_width, window_height)
            if score >= minimum_score:
                candidates.append(
                    (score, x + window_width // 2, y + window_height // 2)
                )

    selected: list[tuple[int, int, int]] = []
    for score, x, y in sorted(candidates, reverse=True):
        if _rim_score(image, bounds, scale, x, y, window_width, window_height) < 0.34:
            continue
        if any(
            abs(x - other_x) < window_width * 0.72
            and abs(y - other_y) < window_height * 0.8
            for _, other_x, other_y in selected
        ):
            continue
        selected.append((score, x, y))

    if len(selected) < 3:
        raise BoardDetectionError("Không nhận diện được ít nhất 3 miệng ống.")

    rows: list[list[tuple[int, int, int]]] = []
    row_tolerance = max(window_height * 1.4, width * 0.045)
    for candidate in sorted(selected, key=lambda item: item[2]):
        if not rows or candidate[2] - sum(row[2] for row in rows[-1]) / len(rows[-1]) > row_tolerance:
            rows.append([candidate])
        else:
            rows[-1].append(candidate)

    tube_rows = [row for row in rows if len(row) >= 2]
    if not tube_rows:
        raise BoardDetectionError("Không tìm thấy các hàng ống trên bàn chơi.")

    mouths = []
    for row in tube_rows:
        for _, x, y in sorted(row, key=lambda item: item[1]):
            mouths.append((x0 + x, y0 + y, window_width))
    return tuple(mouths)


def _sample_color(
    image: RGBImage,
    x: int,
    y: int,
    scale: int,
) -> tuple[int, int, int]:
    radius = max(1, scale)
    samples = [[], [], []]
    for dy in range(-radius, radius + 1, max(1, radius)):
        for dx in range(-radius, radius + 1, max(1, radius)):
            px = min(max(0, x + dx), image.size[0] - 1)
            py = min(max(0, y + dy), image.size[1] - 1)
            color = image.getpixel((px, py))
            for channel, value in zip(samples, color):
                channel.append(value)
    return tuple(sorted(channel)[len(channel) // 2] for channel in samples)


def _same_color(first: tuple[int, int, int], second: tuple[int, int, int]) -> bool:
    first_h, first_s, first_v = colorsys.rgb_to_hsv(*(value / 255 for value in first))
    second_h, second_s, second_v = colorsys.rgb_to_hsv(*(value / 255 for value in second))
    if first_s < 0.16 and second_s < 0.16:
        return abs(first_v - second_v) < 0.32
    hue_difference = abs(first_h - second_h)
    hue_difference = min(hue_difference, 1 - hue_difference)
    return hue_difference < 0.025 and abs(first_s - second_s) < 0.45


def detect_water_sort_board(image: RGBImage) -> tuple[
    tuple[tuple[str, ...], ...],
    tuple[tuple[int, int], ...],
]:
    scale = max(1, math.ceil(max(image.size) / 1400))
    game_bounds = _game_bounds(image, scale)
    mouths = _find_tube_mouths(image, game_bounds, scale)
    color_palette: list[tuple[int, int, int]] = []
    tubes: list[tuple[str, ...]] = []
    positions: list[tuple[int, int]] = []

    for tube_number, (mouth_x, mouth_y, mouth_width) in enumerate(mouths, start=1):
        body_top = mouth_y + round(mouth_width * 0.34)
        body_height = round(mouth_width * 2.8)
        slot_height = body_height / 4
        top_to_bottom = []
        for slot in range(4):
            sample_y = round(body_top + (slot + 0.5) * slot_height) * scale
            sample_x = mouth_x * scale
            color = _sample_color(image, sample_x, sample_y, scale)
            top_to_bottom.append(None if _is_background(color) else color)

        seen_liquid = False
        top_to_bottom_symbols = []
        for color in top_to_bottom:
            if color is None:
                if seen_liquid:
                    raise BoardDetectionError(
                        f"Phát hiện ô trống xen giữa các lớp màu ở ống {tube_number}; "
                        "hãy kiểm tra bố cục bàn chơi."
                    )
                continue
            seen_liquid = True
            color_index = next(
                (index for index, known in enumerate(color_palette) if _same_color(color, known)),
                None,
            )
            if color_index is None:
                if len(color_palette) >= 26:
                    raise BoardDetectionError("Nhận diện quá nhiều màu; hãy kiểm tra ảnh chụp.")
                color_palette.append(color)
                color_index = len(color_palette) - 1
            top_to_bottom_symbols.append(chr(ord("A") + color_index))

        tubes.append(tuple(reversed(top_to_bottom_symbols)))
        click_y = mouth_y + round(mouth_width * 1.7)
        positions.append((mouth_x * scale, click_y * scale))

    return tuple(tubes), tuple(positions)
