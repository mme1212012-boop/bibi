import threading
import unittest

from water_sort import Move
from water_sort_automation import execute_moves, parse_tube_positions


class WaterSortAutomationTests(unittest.TestCase):
    def test_parse_tube_positions(self):
        positions = parse_tube_positions("100,300; 180,300;260,300", 3, 400, 600)
        self.assertEqual(positions, ((100, 300), (180, 300), (260, 300)))

    def test_parse_rejects_missing_or_out_of_bounds_positions(self):
        with self.assertRaisesRegex(ValueError, "đủ 3 ống"):
            parse_tube_positions("100,300;180,300", 3, 400, 600)
        with self.assertRaisesRegex(ValueError, "nằm ngoài"):
            parse_tube_positions("100,300;400,300;260,300", 3, 400, 600)

    def test_execute_clicks_source_then_target_for_each_move(self):
        moves = [Move(1, 2, "R", 2), Move(3, 1, "G", 1)]
        clicked = []

        completed = execute_moves(moves, clicked.append, threading.Event(), delay_seconds=0)

        self.assertTrue(completed)
        self.assertEqual(clicked, [1, 2, 3, 1])

    def test_execute_stops_after_stop_is_requested(self):
        stop_event = threading.Event()
        clicked = []

        def click_tube(tube_number):
            clicked.append(tube_number)
            stop_event.set()

        completed = execute_moves(
            [Move(1, 2, "R", 1)],
            click_tube,
            stop_event,
            delay_seconds=0,
        )

        self.assertFalse(completed)
        self.assertEqual(clicked, [1])


if __name__ == "__main__":
    unittest.main()
