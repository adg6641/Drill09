"""실제 SDL 이벤트·PNG 로드·32프레임 렌더링 검증.

python tests/smoke_pico2d.py
python tests/smoke_pico2d.py --output 검증이미지폴더

SDL dummy 드라이버와 소프트웨어 렌더러를 사용하므로 창을 띄우지 않는다.
"""

import argparse
import ctypes
import hashlib
import importlib
import os
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch
import zlib

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import animation_drill09 as game
import pico2d as pico

native = importlib.import_module("pico2d.pico2d")


def write_png(path, width, height, pixels):
    def chunk(kind, content):
        payload = kind + content
        return (struct.pack(">I", len(content)) + payload
                + struct.pack(">I", zlib.crc32(payload) & 0xffffffff))

    stride = width * 3
    rows = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride]
                    for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def read_pixels():
    width, height = game.CANVAS_WIDTH, game.CANVAS_HEIGHT
    buffer = (ctypes.c_ubyte * (width * height * 3))()
    result = native.SDL_RenderReadPixels(
        native.renderer, None, pico.SDL_PIXELFORMAT_RGB24, buffer, width * 3)
    if result != 0:
        raise RuntimeError(pico.SDL_GetError().decode("utf-8"))
    return bytes(buffer)


def push_event(kind, key=None):
    event = pico.SDL_Event()
    event.type = kind
    if key is not None:
        event.key.keysym.sym = key
        event.key.repeat = 0
    if pico.SDL_PushEvent(ctypes.byref(event)) != 1:
        raise RuntimeError("SDL 이벤트를 넣지 못했습니다.")


def verify_main_loop(output):
    schedule = [[] for _ in range(60)]
    schedule[10] = [(pico.SDL_KEYDOWN, pico.SDLK_RIGHT)]
    schedule[20] = [(pico.SDL_KEYUP, pico.SDLK_RIGHT), (pico.SDL_KEYDOWN, pico.SDLK_UP)]
    schedule[30] = [(pico.SDL_KEYUP, pico.SDLK_UP), (pico.SDL_KEYDOWN, pico.SDLK_LEFT)]
    schedule[40] = [(pico.SDL_KEYUP, pico.SDLK_LEFT), (pico.SDL_KEYDOWN, pico.SDLK_DOWN)]
    schedule[50] = [(pico.SDL_KEYUP, pico.SDLK_DOWN)]
    schedule.append([(pico.SDL_QUIT, None)])
    batches = iter(schedule)
    actual_events, actual_draw = pico.get_events, game.draw_scene
    actual_present, actual_close = pico.update_canvas, pico.close_canvas
    observations = []
    elapsed = 0.0

    def events():
        for kind, key in next(batches):
            push_event(kind, key)
        return actual_events()

    def clock():
        nonlocal elapsed
        elapsed += 0.05
        return elapsed

    def draw(background, sprite, boy, api):
        observations.append((boy.x, boy.y, boy.facing, boy.moving))
        actual_draw(background, sprite, boy, api)

    def present():
        if len(observations) == 37:
            write_png(output / "animation_preview.png", 800, 600, read_pixels())
        actual_present()

    with patch.object(pico, "get_events", side_effect=events), \
            patch.object(game, "perf_counter", side_effect=clock), \
            patch.object(game, "draw_scene", side_effect=draw), \
            patch.object(pico, "update_canvas", side_effect=present), \
            patch.object(pico, "delay"), \
            patch.object(pico, "close_canvas", wraps=actual_close) as close:
        game.main()
        close.assert_called_once()

    expected = {
        9: (400, 300, game.RIGHT, False),
        19: (520, 300, game.RIGHT, True),
        29: (520, 420, game.RIGHT, True),
        39: (400, 420, game.LEFT, True),
        49: (400, 300, game.LEFT, True),
        59: (400, 300, game.LEFT, False),
    }
    assert len(observations) == 60
    for index, target in expected.items():
        actual = observations[index]
        assert abs(actual[0] - target[0]) < 1e-7, (index, actual, target)
        assert abs(actual[1] - target[1]) < 1e-7, (index, actual, target)
        assert actual[2:] == target[2:], (index, actual, target)
    print("PASS: actual SDL arrows, idle/run, vertical facing, 60 main-loop frames, quit cleanup")


def verify_sprite_frames(output):
    pico.open_canvas(800, 600)
    try:
        background = pico.load_image(str(game.RESOURCE_DIR / "TUK_GROUND.png"))
        sprite = pico.load_image(str(game.RESOURCE_DIR / "animation_sheet.png"))
        sheet = bytearray(800 * 400 * 3)
        modes = ((False, game.RIGHT), (False, game.LEFT),
                 (True, game.RIGHT), (True, game.LEFT))
        for row, (moving, facing) in enumerate(modes):
            hashes = set()
            for frame in range(8):
                boy = game.Boy(moving=moving, facing=facing, frame=frame)
                # present 전에 실제 렌더 버퍼를 읽는다.
                with patch.object(pico, "update_canvas"):
                    game.draw_scene(background, sprite, boy, pico)
                pixels = read_pixels()
                tile = bytearray()
                for y in range(100):
                    start = ((250 + y) * 800 + 350) * 3
                    line = pixels[start:start + 300]
                    tile.extend(line)
                    destination = ((row * 100 + y) * 800 + frame * 100) * 3
                    sheet[destination:destination + 300] = line
                hashes.add(hashlib.sha256(tile).hexdigest())
            assert len(hashes) > 1, (moving, facing, "frames did not change")
        write_png(output / "sprite_frames_preview.png", 800, 400, bytes(sheet))
    finally:
        pico.close_canvas()
    print("PASS: both PNG assets and all 32 actual sprite frames rendered")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="drill09-render-"))
    output.mkdir(parents=True, exist_ok=True)
    create_renderer = native.SDL_CreateRenderer

    def software_renderer(window, index, flags):
        return create_renderer(window, index, pico.SDL_RENDERER_SOFTWARE)

    with patch.object(native, "SDL_CreateRenderer", side_effect=software_renderer):
        verify_main_loop(output)
        verify_sprite_frames(output)
    print(f"검증 이미지: {output}")


if __name__ == "__main__":
    main()
