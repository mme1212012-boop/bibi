from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable


TUBE_CAPACITY = 4
MAX_SEARCH_STATES = 300_000


@dataclass(frozen=True)
class Move:
    source: int
    target: int
    color: str
    amount: int


def parse_tubes(text: str) -> tuple[tuple[str, ...], ...]:
    tubes = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        contents = line.strip().replace(" ", "")
        if not contents:
            continue
        if contents in {"-", "_"}:
            tubes.append(())
            continue
        if len(contents) > TUBE_CAPACITY:
            raise ValueError(f"Ống {line_number} có hơn {TUBE_CAPACITY} ô.")
        tubes.append(tuple(contents.upper()))

    if not tubes:
        raise ValueError("Hãy nhập trạng thái các ống, mỗi ống một dòng.")

    counts: dict[str, int] = {}
    for tube in tubes:
        for color in tube:
            counts[color] = counts.get(color, 0) + 1
    if any(count != TUBE_CAPACITY for count in counts.values()):
        raise ValueError("Mỗi màu phải có đúng 4 ô để có thể giải.")
    if len(tubes) < len(counts) + 1:
        raise ValueError("Cần ít nhất một ống trống ngoài các màu.")
    return tuple(tubes)


def is_solved(tubes: tuple[tuple[str, ...], ...]) -> bool:
    return all(not tube or (len(tube) == TUBE_CAPACITY and len(set(tube)) == 1) for tube in tubes)


def _top_run(tube: tuple[str, ...]) -> tuple[str, int]:
    color = tube[-1]
    amount = 1
    while amount < len(tube) and tube[-amount - 1] == color:
        amount += 1
    return color, amount


def solve_water_sort(
    start: tuple[tuple[str, ...], ...],
    progress: Callable[[int], None] | None = None,
) -> list[Move] | None:
    if is_solved(start):
        return []

    parents: dict[
        tuple[tuple[str, ...], ...],
        tuple[tuple[tuple[str, ...], ...] | None, Move | None],
    ] = {start: (None, None)}
    queue = deque([start])
    visited = {tuple(sorted(start))}

    while queue:
        state = queue.popleft()
        if is_solved(state):
            path = []
            while parents[state][0] is not None:
                parent, move = parents[state]
                assert parent is not None and move is not None
                path.append(move)
                state = parent
            return list(reversed(path))

        for source_index, source in enumerate(state):
            if not source or (len(source) == TUBE_CAPACITY and len(set(source)) == 1):
                continue
            color, run_size = _top_run(source)
            empty_seen = False
            for target_index, target in enumerate(state):
                if source_index == target_index or len(target) == TUBE_CAPACITY:
                    continue
                if target and target[-1] != color:
                    continue
                if not target:
                    if empty_seen:
                        continue
                    empty_seen = True
                    if len(source) == run_size:
                        continue

                amount = min(run_size, TUBE_CAPACITY - len(target))
                next_tubes = list(state)
                next_tubes[source_index] = source[:-amount]
                next_tubes[target_index] = target + (color,) * amount
                next_state = tuple(next_tubes)
                key = tuple(sorted(next_state))
                if key in visited:
                    continue
                visited.add(key)
                move = Move(source_index + 1, target_index + 1, color, amount)
                parents[next_state] = (state, move)
                queue.append(next_state)

                if progress and len(visited) % 10_000 == 0:
                    progress(len(visited))
                if len(visited) >= MAX_SEARCH_STATES:
                    return None

    return None
