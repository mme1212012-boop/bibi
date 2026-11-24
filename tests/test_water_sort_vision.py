import unittest

from PIL import Image, ImageDraw

from water_sort import parse_tubes
from water_sort import Move
from water_sort_vision import (
    BoardDetectionError,
    annotate_water_sort_guidance,
    detect_water_sort_board,
)


def _sample_board() -> Image.Image:
    image = Image.new("RGB", (360, 318), (184, 190, 255))
    draw = ImageDraw.Draw(image)
    color_values = {
        "A": (0, 168, 232),
        "B": (78, 205, 196),
        "C": (233, 30, 156),
        "D": (14, 155, 114),
        "E": (107, 107, 107),
        "F": (242, 141, 130),
    }
    tube_specs = [
        (65, 58, "AABB"),
        (118, 58, "CCCB"),
        (171, 58, "DDDB"),
        (224, 58, "EEE"),
        (277, 58, "FFDF"),
        (55, 173, ""),
        (143, 157, "AAF"),
        (200, 157, "EC"),
    ]
    cap_width = 31
    body_height = round(cap_width * 2.8)
    slot_height = body_height / 4
    for center_x, cap_y, bottom_to_top in tube_specs:
        body_top = cap_y + 11
        body_bottom = body_top + body_height
        draw.rectangle(
            (center_x - 19, body_top, center_x + 19, body_bottom),
            fill=(184, 190, 255),
            outline=(255, 255, 255),
            width=2,
        )
        top_to_bottom = [None] * (4 - len(bottom_to_top)) + list(
            reversed(bottom_to_top)
        )
        for slot, color in enumerate(top_to_bottom):
            if color:
                y0 = round(body_top + slot * slot_height) + 1
                y1 = round(body_top + (slot + 1) * slot_height) - 1
                draw.rectangle(
                    (center_x - 16, y0, center_x + 16, y1),
                    fill=color_values[color],
                )
        draw.ellipse(
            (center_x - 14, cap_y - 8, center_x + 14, cap_y + 8),
            fill=(184, 190, 255),
            outline=(255, 255, 255),
            width=4,
        )
    return image


class WaterSortVisionTests(unittest.TestCase):
    def test_detects_two_rows_colors_empty_tubes_and_click_positions(self):
        image = _sample_board()
        tubes, positions = detect_water_sort_board(image)

        self.assertEqual(
            tubes,
            (
                ("B", "B", "A", "A"),
                ("C", "C", "C", "A"),
                ("D", "D", "D", "A"),
                ("E", "E", "E"),
                ("F", "F", "D", "F"),
                (),
                ("B", "B", "F"),
                ("E", "C"),
            ),
        )
        self.assertEqual(sum(not tube for tube in tubes), 1)
        self.assertTrue(all(len(tube) <= 4 for tube in tubes))
        self.assertEqual(len(positions), 8)
        expected_x = (65, 118, 171, 224, 277, 55, 143, 200)
        self.assertTrue(
            all(
                abs(actual[0] - expected) <= 4
                for actual, expected in zip(positions, expected_x)
            )
        )
        self.assertEqual(parse_tubes("\n".join("".join(tube) or "-" for tube in tubes)), tubes)

    def test_positions_are_relative_to_the_full_emulator_capture(self):
        board = _sample_board()
        screenshot = Image.new("RGB", (900, 600), (0, 0, 0))
        screenshot.paste(board, (270, 120))

        _, positions = detect_water_sort_board(screenshot)

        self.assertEqual(len(positions), 8)
        self.assertTrue(all(x >= 270 and y >= 120 for x, y in positions))
        self.assertTrue(abs(positions[0][0] - 335) <= 4)

    def test_rejects_an_image_without_tube_mouths(self):
        image = Image.new("RGB", (360, 318), (184, 190, 255))

        with self.assertRaises(BoardDetectionError):
            detect_water_sort_board(image)

    def test_guidance_overlay_marks_source_red_and_target_green(self):
        image = Image.new("RGB", (360, 318), (0, 0, 0))
        positions = ((80, 100), (180, 100))

        annotated = annotate_water_sort_guidance(
            image,
            positions,
            Move(source=1, target=2, color="A", amount=2),
        )

        self.assertEqual(annotated.size, image.size)
        self.assertEqual(annotated.getpixel((80, 100)), (255, 45, 45))
        self.assertEqual(annotated.getpixel((180, 100)), (45, 220, 90))


if __name__ == "__main__":
    unittest.main()
