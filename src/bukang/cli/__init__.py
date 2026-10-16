"""사용자 입력과 도움말을 담당하는 CLI 계층."""

import shutil

import click

from .image import render_bukang_image


class BukangGroup(click.Group):
    """도움말 앞에 부캉이 픽셀 그림을 표시한다."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """터미널 너비에 맞춘 그림과 기본 도움말을 작성한다."""
        width = max(1, min(44, shutil.get_terminal_size().columns - 2))
        formatter.write(render_bukang_image(width) + "\n\n")
        super().format_help(ctx, formatter)


@click.group(cls=BukangGroup, invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """부캉이가 만들어주는 컨테이너 런타임."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help(), color=ctx.color)
