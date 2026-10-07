"""Drill #9: 방향키 이동, 좌우 방향 유지, IDLE/RUN 스프라이트 애니메이션.

실행: python animation_drill09.py
조작: 방향키로 이동, Esc 또는 창 닫기로 종료.
개발 기록과 검증 결과: development_report.md 및 git log --oneline.
"""

from dataclasses import dataclass, field
from math import hypot
from pathlib import Path
from time import perf_counter


CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
FRAME_WIDTH = 100
FRAME_HEIGHT = 100
SPRITE_MARGIN = 1
MOVE_SPEED = 240.0  # 픽셀/초
MAX_FRAME_TIME = 0.1
RESOURCE_DIR = Path(__file__).resolve().parent

LEFT, RIGHT, UP, DOWN = "left", "right", "up", "down"
ARROW_KEYS = frozenset((LEFT, RIGHT, UP, DOWN))


@dataclass
class Boy:
    """그래픽 라이브러리와 독립적으로 입력과 소년의 상태를 계산한다."""

    x: float = CANVAS_WIDTH / 2
    y: float = CANVAS_HEIGHT / 2
    facing: str = RIGHT
    moving: bool = False
    pressed_keys: set[str] = field(default_factory=set)

    def press(self, key: str) -> None:
        if key in ARROW_KEYS:
            self.pressed_keys.add(key)

    def release(self, key: str) -> None:
        self.pressed_keys.discard(key)

    def update(self, delta_time: float) -> None:
        if delta_time < 0:
            raise ValueError("경과시간은 음수일 수 없습니다.")

        dx = int(RIGHT in self.pressed_keys) - int(LEFT in self.pressed_keys)
        dy = int(UP in self.pressed_keys) - int(DOWN in self.pressed_keys)
        if dx:
            self.facing = RIGHT if dx > 0 else LEFT

        old_x, old_y = self.x, self.y
        length = hypot(dx, dy)
        if length:
            distance = MOVE_SPEED * delta_time / length
            self.x += dx * distance
            self.y += dy * distance
        self.moving = (self.x, self.y) != (old_x, old_y)


def handle_events(events, boy: Boy, pico) -> bool:
    """누른 키를 갱신하고 계속 실행할지 반환한다."""
    key_map = {
        pico.SDLK_LEFT: LEFT,
        pico.SDLK_RIGHT: RIGHT,
        pico.SDLK_UP: UP,
        pico.SDLK_DOWN: DOWN,
    }
    for event in events:
        if event.type == pico.SDL_QUIT:
            return False
        if event.type == pico.SDL_KEYDOWN:
            if event.key == pico.SDLK_ESCAPE:
                return False
            if event.key in key_map:
                boy.press(key_map[event.key])
        elif event.type == pico.SDL_KEYUP and event.key in key_map:
            boy.release(key_map[event.key])
    return True


def draw_scene(background, sprite, boy: Boy, pico) -> None:
    pico.clear_canvas()
    background.draw(
        CANVAS_WIDTH / 2, CANVAS_HEIGHT / 2, CANVAS_WIDTH, CANVAS_HEIGHT
    )
    bottom = SPRITE_MARGIN + (FRAME_HEIGHT if boy.facing == RIGHT else 0)
    sprite.clip_draw(
        SPRITE_MARGIN, bottom, FRAME_WIDTH, FRAME_HEIGHT, boy.x, boy.y
    )
    pico.update_canvas()


def main() -> None:
    # import만으로 창을 열지 않아 규칙 테스트를 독립적으로 실행할 수 있다.
    import pico2d as pico

    background_path = RESOURCE_DIR / "TUK_GROUND.png"
    sprite_path = RESOURCE_DIR / "animation_sheet.png"
    for path in (background_path, sprite_path):
        if not path.is_file():
            raise FileNotFoundError(f"실행 파일 옆에 필요한 이미지가 없습니다: {path}")

    pico.open_canvas(CANVAS_WIDTH, CANVAS_HEIGHT)
    try:
        background = pico.load_image(str(background_path))
        sprite = pico.load_image(str(sprite_path))
        boy = Boy()
        previous_time = perf_counter()

        while handle_events(pico.get_events(), boy, pico):
            current_time = perf_counter()
            delta_time = min(current_time - previous_time, MAX_FRAME_TIME)
            previous_time = current_time
            boy.update(delta_time)
            draw_scene(background, sprite, boy, pico)
            pico.delay(1 / 60)
    finally:
        pico.close_canvas()


if __name__ == "__main__":
    main()
