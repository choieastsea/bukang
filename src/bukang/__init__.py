"""Bukang's terminal welcome screen."""

import json
from functools import cache
from importlib.resources import files

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Static


@cache
def load_pixels() -> tuple[tuple[str, ...], ...]:
    """Read the precomputed RGB pixels once per process."""
    data = json.loads(files("bukang").joinpath("bukang.pixels.json").read_text())
    return tuple(
        tuple("#" + row[x:x + 6] for x in range(0, len(row), 6))
        for row in data["rows"]
    )


def render_bukang_image(width: int) -> Text:
    """Fit saved pixels to the terminal, drawing two pixels per cell."""
    pixels = load_pixels()
    source_height, source_width = len(pixels), len(pixels[0])
    height = max(2, round(width * source_height / source_width / 2) * 2)
    result = Text(no_wrap=True)
    for y in range(0, height, 2):
        for x in range(width):
            source_x = x * source_width // width
            top = pixels[y * source_height // height][source_x]
            bottom = pixels[(y + 1) * source_height // height][source_x]
            result.append(
                "▀",
                Style(
                    color=top,
                    bgcolor=bottom,
                ),
            )
        if y + 2 < height:
            result.append("\n")
    return result


class BukangApp(App):
    """A welcome screen; container operations will be added separately."""

    TITLE = "bukang"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [("q", "quit", "종료"), ("ctrl+c", "quit", "종료")]

    CSS = """
    $paper: #ffffff;
    $ink: #16354b;
    $sea: #2389bd;
    $muted: #647887;
    Screen { background: $paper; color: $ink; }
    #welcome { height: 1fr; align: center middle; padding: 1 2; }
    #brand { height: 1; text-align: center; text-style: bold; color: $sea; }
    #mascot { width: 1fr; height: auto; text-align: center; margin: 1 0; }
    #greeting { height: auto; text-align: center; text-style: bold; }
    #tagline { height: auto; text-align: center; color: $muted; margin-top: 1; }
    Footer { background: $paper; color: $muted; }
    FooterKey { background: $paper; }
    FooterKey > .footer-key--key { background: $paper; color: $sea; }
    FooterKey > .footer-key--description { background: $paper; color: $muted; }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="welcome"):
            yield Static("B U K A N G", id="brand")
            yield Static(id="mascot")
            yield Static("부캉이는 나가고 싶지 않다.", id="greeting")
            yield Static("부캉이가 만들어주는 컨테이너 런타임", id="tagline")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_bukang_image()

    def on_resize(self) -> None:
        if self.is_mounted:
            self.refresh_bukang_image()

    def refresh_bukang_image(self) -> None:
        width = max(8, min(44, self.size.width - 6, (self.size.height - 10) * 2))
        self.query_one("#mascot", Static).update(render_bukang_image(width))


def main() -> None:
    BukangApp().run()
