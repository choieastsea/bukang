"""사용자 입력과 도움말을 담당하는 CLI 계층"""

import shutil

import click

from .image import render_bukang_image


class BukangGroup(click.Group):
    """부캉이 그림과 한글 도움말을 표시한다"""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """부캉이의 소개와 사용법, 구현 예정 명령을 안내한다"""
        width = max(1, min(44, shutil.get_terminal_size().columns - 2))
        formatter.write(render_bukang_image(width) + "\n\n")
        formatter.write_text("🦈 컨테이너를 만드는 상어, 부캉이다크아앙!")
        formatter.write_text("격리된 공간을 만드는 과정을 하나씩 알려드린다부우우-")
        formatter.write_paragraph()
        formatter.write_usage(ctx.command_path, "[옵션]", prefix="사용법: ")
        with formatter.section("옵션"):
            formatter.write_dl([
                record
                for param in self.get_params(ctx)
                if (record := param.get_help_record(ctx)) is not None
            ])
        with formatter.section("준비 중인 명령"):
            formatter.write_dl([
                ("run", "컨테이너를 실행하고, 끝날 때까지 기다린다부우우-"),
                ("run -d", "컨테이너를 백그라운드로 실행한다크아앙!"),
                ("ps", "컨테이너 목록과 실행 상태를 보여드린다부우우-"),
                ("stop", "컨테이너에 종료를 요청한다크아앙!"),
                ("rm", "종료된 컨테이너의 파일과 남은 자원을 정리한다부우우-"),
            ])
        formatter.write_paragraph()
        formatter.write_text("아직은 도움말만 볼 수 있고, 위 명령은 차근차근 준비한다부우우-")


@click.group(cls=BukangGroup, invoke_without_command=True)
@click.help_option("--help", help="부캉이의 사용 안내를 보여드린다부우우-")
@click.pass_context
def main(ctx: click.Context) -> None:
    """부캉이가 만들어주는 컨테이너 런타임"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help(), color=ctx.color)
