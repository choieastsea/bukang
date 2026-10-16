"""저장된 부캉이 픽셀을 터미널 문자로 표시한다."""

import json
from functools import cache
from importlib.resources import files

import click


@cache
def load_pixels() -> tuple[tuple[tuple[int, ...], ...], ...]:
    """픽셀 데이터를 한 번 읽어 RGB 값으로 보관한다."""
    data = json.loads(files("bukang").joinpath("bukang.pixels.json").read_text())
    return tuple(
        tuple(tuple(bytes.fromhex(row[x:x + 6])) for x in range(0, len(row), 6))
        for row in data["rows"]
    )


def render_bukang_image(width: int) -> str:
    """위아래 두 픽셀을 한 글자에 담아 지정한 너비로 그린다."""
    pixels = load_pixels()
    source_height, source_width = len(pixels), len(pixels[0])
    height = max(2, round(width * source_height / source_width / 2) * 2)
    lines = []
    for y in range(0, height, 2):
        line = []
        for x in range(width):
            source_x = x * source_width // width
            top = pixels[y * source_height // height][source_x]
            bottom = pixels[(y + 1) * source_height // height][source_x]
            line.append(click.style("▀", fg=top, bg=bottom))
        lines.append("".join(line))
    return "\n".join(lines)
