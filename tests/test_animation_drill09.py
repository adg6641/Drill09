"""채점 요구사항과 입력·상태 전환의 회귀 테스트 (외부 패키지 불필요)."""

import importlib
import math
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import animation_drill09 as game


def event_api():
    return SimpleNamespace(
        SDL_QUIT=1, SDL_KEYDOWN=2, SDL_KEYUP=3,
        SDLK_LEFT=10, SDLK_RIGHT=11, SDLK_UP=12, SDLK_DOWN=13, SDLK_ESCAPE=14,
    )


class MovementTests(unittest.TestCase):
    def test_four_arrow_directions(self):
        cases = {
            game.LEFT: (376, 300, game.LEFT),
            game.RIGHT: (424, 300, game.RIGHT),
            game.UP: (400, 324, game.RIGHT),
            game.DOWN: (400, 276, game.RIGHT),
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                boy = game.Boy()
                boy.press(key)
                boy.update(0.1)
                self.assertEqual((boy.x, boy.y, boy.facing), expected)
                self.assertTrue(boy.moving)

    def test_vertical_movement_preserves_both_facings(self):
        for facing in (game.LEFT, game.RIGHT):
            for key in (game.UP, game.DOWN):
                with self.subTest(facing=facing, key=key):
                    boy = game.Boy(facing=facing)
                    boy.press(key)
                    boy.update(0.1)
                    self.assertEqual(boy.facing, facing)
                    self.assertTrue(boy.moving)

    def test_repeated_keydown_then_one_release_stops(self):
        boy = game.Boy()
        for _ in range(20):
            boy.press(game.RIGHT)
        boy.update(0.1)
        old_position = (boy.x, boy.y)
        boy.release(game.RIGHT)
        boy.update(0.1)
        self.assertEqual((boy.x, boy.y), old_position)
        self.assertFalse(boy.moving)

    def test_opposite_keys_cancel_then_remaining_key_moves(self):
        boy = game.Boy(facing=game.LEFT)
        boy.press(game.LEFT)
        boy.press(game.RIGHT)
        boy.update(0.1)
        self.assertEqual((boy.x, boy.y, boy.facing), (400, 300, game.LEFT))
        self.assertFalse(boy.moving)
        boy.release(game.LEFT)
        boy.update(0.1)
        self.assertEqual((boy.x, boy.facing), (424, game.RIGHT))

    def test_four_keys_cancel_both_axes(self):
        boy = game.Boy()
        for key in game.ARROW_KEYS:
            boy.press(key)
        boy.update(0.1)
        self.assertEqual((boy.x, boy.y), (400, 300))
        self.assertFalse(boy.moving)

    def test_releasing_one_axis_preserves_other_axis(self):
        boy = game.Boy()
        boy.press(game.LEFT)
        boy.press(game.UP)
        boy.update(0.1)
        boy.release(game.LEFT)
        old_x, old_y = boy.x, boy.y
        boy.update(0.1)
        self.assertEqual(boy.x, old_x)
        self.assertEqual(boy.y, old_y + 24)
        self.assertEqual(boy.facing, game.LEFT)

    def test_diagonal_speed_matches_axis_speed(self):
        boy = game.Boy()
        boy.press(game.RIGHT)
        boy.press(game.UP)
        boy.update(0.1)
        self.assertAlmostEqual(math.hypot(boy.x - 400, boy.y - 300), 24)

    def test_elapsed_time_is_independent_of_update_count(self):
        one, many = game.Boy(), game.Boy()
        one.press(game.RIGHT)
        many.press(game.RIGHT)
        one.update(0.5)
        for _ in range(50):
            many.update(0.01)
        self.assertAlmostEqual(one.x, many.x)

    def test_unrelated_keys_and_unmatched_release_are_ignored(self):
        boy = game.Boy()
        boy.press("space")
        boy.release(game.LEFT)
        boy.update(0.1)
        self.assertEqual(boy.pressed_keys, set())
        self.assertFalse(boy.moving)


class BoundaryTests(unittest.TestCase):
    def assert_inside(self, boy):
        self.assertGreaterEqual(boy.x - game.FRAME_WIDTH / 2, 0)
        self.assertLessEqual(boy.x + game.FRAME_WIDTH / 2, game.CANVAS_WIDTH)
        self.assertGreaterEqual(boy.y - game.FRAME_HEIGHT / 2, 0)
        self.assertLessEqual(boy.y + game.FRAME_HEIGHT / 2, game.CANVAS_HEIGHT)

    def test_four_edges_stop_even_with_large_elapsed_time(self):
        cases = {
            game.LEFT: (50, 300), game.RIGHT: (750, 300),
            game.UP: (400, 550), game.DOWN: (400, 50),
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                boy = game.Boy()
                boy.press(key)
                boy.update(10)
                self.assertEqual((boy.x, boy.y), expected)
                self.assert_inside(boy)
                boy.update(10)
                self.assertEqual((boy.x, boy.y), expected)
                self.assertFalse(boy.moving)

    def test_all_corners_keep_the_whole_sprite_inside(self):
        for horizontal, x in ((game.LEFT, 50), (game.RIGHT, 750)):
            for vertical, y in ((game.DOWN, 50), (game.UP, 550)):
                with self.subTest(horizontal=horizontal, vertical=vertical):
                    boy = game.Boy()
                    boy.press(horizontal)
                    boy.press(vertical)
                    boy.update(10)
                    self.assertEqual((boy.x, boy.y), (x, y))
                    self.assert_inside(boy)
                    boy.update(10)
                    self.assertFalse(boy.moving)

    def test_can_move_back_from_each_edge(self):
        pairs = ((game.LEFT, game.RIGHT), (game.RIGHT, game.LEFT),
                 (game.UP, game.DOWN), (game.DOWN, game.UP))
        for outward, inward in pairs:
            with self.subTest(outward=outward):
                boy = game.Boy()
                boy.press(outward)
                boy.update(10)
                old_position = (boy.x, boy.y)
                boy.release(outward)
                boy.press(inward)
                boy.update(0.1)
                self.assertNotEqual((boy.x, boy.y), old_position)
                self.assertTrue(boy.moving)
                self.assert_inside(boy)

    def test_can_move_along_a_blocked_edge(self):
        boy = game.Boy(x=750)
        boy.press(game.RIGHT)
        boy.press(game.UP)
        boy.update(0.1)
        self.assertEqual(boy.x, 750)
        self.assertGreater(boy.y, 300)
        self.assertTrue(boy.moving)
        self.assert_inside(boy)


class AnimationTests(unittest.TestCase):
    def test_initial_idle_animates_and_wraps(self):
        boy = game.Boy()
        boy.update(1 / game.IDLE_FPS)
        self.assertEqual(boy.frame, 1)
        self.assertFalse(boy.moving)
        boy.update(7 / game.IDLE_FPS)
        self.assertEqual(boy.frame, 0)

    def test_idle_animation_after_releasing_horizontal_key(self):
        for key in (game.LEFT, game.RIGHT):
            with self.subTest(key=key):
                boy = game.Boy()
                boy.press(key)
                boy.update(0.1)
                boy.release(key)
                boy.update(0.1)
                self.assertFalse(boy.moving)
                self.assertEqual(boy.facing, key)
                self.assertEqual(boy.frame, 0)
                boy.update(1 / game.IDLE_FPS)
                self.assertEqual(boy.frame, 1)

    def test_running_animation_progresses_and_wraps(self):
        boy = game.Boy()
        boy.press(game.UP)
        boy.update(0.01)
        boy.update(1 / game.RUN_FPS)
        self.assertEqual(boy.frame, 1)
        boy.update(7 / game.RUN_FPS)
        self.assertEqual(boy.frame, 0)
        self.assertTrue(boy.moving)

    def test_facing_change_restarts_animation(self):
        boy = game.Boy()
        boy.press(game.RIGHT)
        boy.update(0.01)
        boy.update(1 / game.RUN_FPS)
        boy.release(game.RIGHT)
        boy.press(game.LEFT)
        boy.update(0.01)
        self.assertEqual((boy.facing, boy.frame, boy.frame_time), (game.LEFT, 0, 0))

    def test_partial_frame_time_is_preserved(self):
        boy = game.Boy()
        boy.update(0.06)
        boy.update(0.065)
        self.assertEqual(boy.frame, 1)
        boy.update(0.02)
        self.assertAlmostEqual(boy.frame_time, 0.02)

    def test_four_animation_rows_and_all_frames_fit_real_asset(self):
        path = game.RESOURCE_DIR / "animation_sheet.png"
        width, height = struct.unpack(">II", path.read_bytes()[16:24])
        expected = {(False, game.RIGHT): 301, (False, game.LEFT): 201,
                    (True, game.RIGHT): 101, (True, game.LEFT): 1}
        for (moving, facing), bottom in expected.items():
            for frame in range(8):
                with self.subTest(moving=moving, facing=facing, frame=frame):
                    boy = game.Boy(moving=moving, facing=facing, frame=frame)
                    left, actual_bottom, w, h = boy.sprite_rectangle()
                    self.assertEqual(actual_bottom, bottom)
                    self.assertEqual((left, w, h), (1 + frame * 100, 100, 100))
                    self.assertGreaterEqual(min(left, actual_bottom), 0)
                    self.assertLessEqual(left + w, width)
                    self.assertLessEqual(actual_bottom + h, height)


class EventAndRenderingTests(unittest.TestCase):
    def test_sdl_key_mapping_and_release(self):
        pico = event_api()
        for code, key in ((pico.SDLK_LEFT, game.LEFT), (pico.SDLK_RIGHT, game.RIGHT),
                          (pico.SDLK_UP, game.UP), (pico.SDLK_DOWN, game.DOWN)):
            with self.subTest(key=key):
                boy = game.Boy()
                self.assertTrue(game.handle_events(
                    [SimpleNamespace(type=pico.SDL_KEYDOWN, key=code)], boy, pico))
                self.assertIn(key, boy.pressed_keys)
                self.assertTrue(game.handle_events(
                    [SimpleNamespace(type=pico.SDL_KEYUP, key=code)], boy, pico))
                self.assertNotIn(key, boy.pressed_keys)

    def test_escape_and_window_close_end_the_loop(self):
        pico = event_api()
        for event in (SimpleNamespace(type=pico.SDL_QUIT),
                      SimpleNamespace(type=pico.SDL_KEYDOWN, key=pico.SDLK_ESCAPE)):
            with self.subTest(event=event):
                self.assertFalse(game.handle_events([event], game.Boy(), pico))

    def test_non_keyboard_event_is_safe(self):
        self.assertTrue(game.handle_events(
            [SimpleNamespace(type=999)], game.Boy(), event_api()))

    def test_background_is_drawn_before_the_boy(self):
        log = Mock()
        pico = SimpleNamespace(clear_canvas=log.clear, update_canvas=log.present)
        background = SimpleNamespace(draw=log.background)
        sprite = SimpleNamespace(clip_draw=log.sprite)
        game.draw_scene(background, sprite, game.Boy(), pico)
        self.assertEqual(log.mock_calls, [
            unittest.mock.call.clear(),
            unittest.mock.call.background(400, 300, 800, 600),
            unittest.mock.call.sprite(1, 301, 100, 100, 400, 300),
            unittest.mock.call.present(),
        ])

    def test_import_does_not_load_pico2d_or_open_a_window(self):
        with patch.dict(sys.modules, {"pico2d": None}):
            importlib.reload(game)
            self.assertEqual(game.Boy().x, 400)

    def test_assets_resolve_from_a_different_working_directory(self):
        expected = Path(game.__file__).resolve().parent
        with patch("os.getcwd", return_value=str(expected.parent)):
            importlib.reload(game)
            self.assertEqual(game.RESOURCE_DIR, expected)
            self.assertTrue((game.RESOURCE_DIR / "TUK_GROUND.png").is_file())

    def test_main_caps_long_frame_time_and_closes_canvas(self):
        pico = event_api()
        pico.open_canvas = Mock()
        pico.close_canvas = Mock()
        pico.load_image = Mock(return_value=Mock())
        pico.get_events = Mock(side_effect=[[], [SimpleNamespace(type=pico.SDL_QUIT)]])
        pico.delay = Mock()
        pico.clear_canvas = Mock()
        pico.update_canvas = Mock()
        with patch.dict(sys.modules, {"pico2d": pico}), \
                patch.object(game, "perf_counter", side_effect=[0, 10]), \
                patch.object(game.Boy, "update") as update:
            game.main()
        update.assert_called_once_with(0.1)
        pico.close_canvas.assert_called_once()

    def test_canvas_closes_if_loading_an_image_fails(self):
        pico = event_api()
        pico.open_canvas = Mock()
        pico.close_canvas = Mock()
        pico.load_image = Mock(side_effect=OSError("image load failed"))
        with patch.dict(sys.modules, {"pico2d": pico}):
            with self.assertRaises(OSError):
                game.main()
        pico.close_canvas.assert_called_once()


if __name__ == "__main__":
    unittest.main()
