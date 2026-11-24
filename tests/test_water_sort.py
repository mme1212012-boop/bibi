import unittest

from water_sort import is_solved, parse_tubes, solve_water_sort


class WaterSortTests(unittest.TestCase):
    def test_parse_accepts_explicit_empty_tubes(self):
        tubes = parse_tubes("RRGG\nGGRR\n-\n_")
        self.assertEqual(tubes, (tuple("RRGG"), tuple("GGRR"), (), ()))

    def test_parse_requires_four_of_each_color(self):
        with self.assertRaisesRegex(ValueError, "đúng 4"):
            parse_tubes("RRG\nGGR\n-\n")

    def test_solver_finds_a_valid_solution(self):
        start = parse_tubes("RRGG\nGGRR\n-\n-")
        moves = solve_water_sort(start)
        self.assertIsNotNone(moves)

        tubes = [list(tube) for tube in start]
        for move in moves:
            source = tubes[move.source - 1]
            target = tubes[move.target - 1]
            self.assertEqual(source[-move.amount:], [move.color] * move.amount)
            self.assertLessEqual(len(target) + move.amount, 4)
            self.assertTrue(not target or target[-1] == move.color)
            del source[-move.amount:]
            target.extend([move.color] * move.amount)

        self.assertTrue(is_solved(tuple(tuple(tube) for tube in tubes)))

    def test_solver_returns_no_moves_for_solved_state(self):
        start = parse_tubes("RRRR\nGGGG\n-")
        self.assertEqual(solve_water_sort(start), [])


if __name__ == "__main__":
    unittest.main()
