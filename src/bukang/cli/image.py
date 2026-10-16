"""저장된 부캉이 픽셀을 터미널 문자로 표시한다"""

import json
from functools import cache
from importlib.resources import files

import click


@cache
def load_pixels() -> tuple[tuple[tuple[int, ...], ...], ...]:
    """픽셀 JSON을 RGB 값으로 읽고, 다음 호출부터는 읽어 둔 값을 반환한다"""
    data = json.loads(files("bukang").joinpath("bukang.pixels.json").read_text())
    # 한 픽셀의 RRGGBB 여섯 글자를 빨강·초록·파랑 세 숫자로 바꾼다
    return tuple(
        tuple(tuple(bytes.fromhex(row[x : x + 6])) for x in range(0, len(row), 6))
        for row in data["rows"]
    )


def render_bukang_image(width: int) -> str:
    """부캉이 그림을 지정한 문자 너비에 맞춰 색이 있는 문자열로 반환한다"""
    pixels = load_pixels()
    source_height, source_width = len(pixels), len(pixels[0])
    # 문자 하나에 위아래 두 픽셀을 넣으므로 픽셀 높이를 짝수로 맞춘다
    height = max(2, round(width * source_height / source_width / 2) * 2)
    lines = []
    for y in range(0, height, 2):
        line = []
        for x in range(width):
            # 출력 위치에 대응하는 원본 픽셀을 골라 그림 크기를 조절한다
            source_x = x * source_width // width
            top = pixels[y * source_height // height][source_x]
            bottom = pixels[(y + 1) * source_height // height][source_x]
            # ▀의 글자색은 위쪽 픽셀, 배경색은 아래쪽 픽셀을 표현한다
            line.append(click.style("▀", fg=top, bg=bottom))
        lines.append("".join(line))
    return "\n".join(lines)
