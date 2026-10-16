"""사용자 입력과 도움말을 담당하는 CLI 계층"""

import shutil
import sys
from pathlib import Path

import click

from .image import render_bukang_image


class BukangGroup(click.Group):
    """부캉이 그림과 한글 도움말을 표시한다"""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """부캉이의 소개와 사용법, 명령을 안내한다"""
        width = max(1, min(44, shutil.get_terminal_size().columns - 2))
        formatter.write(render_bukang_image(width) + "\n\n")
        formatter.write_text("🦈 컨테이너를 만드는 상어, 부캉이다크아앙!")
        formatter.write_text("격리된 공간을 만드는 과정을 하나씩 알려드린다부우우-")
        formatter.write_paragraph()
        formatter.write_usage(ctx.command_path, "[옵션] 명령 [인자]", prefix="사용법: ")
        with formatter.section("옵션"):
            formatter.write_dl([
                record
                for param in self.get_params(ctx)
                if (record := param.get_help_record(ctx)) is not None
            ])
        with formatter.section("명령"):
            formatter.write_dl([
                ("run", "컨테이너를 실행하고, 끝날 때까지 기다린다부우우-"),
            ])
        with formatter.section("준비 중인 명령"):
            formatter.write_dl([
                ("run -d", "컨테이너를 백그라운드로 실행한다크아앙!"),
                ("ps", "컨테이너 목록과 실행 상태를 보여드린다부우우-"),
                ("stop", "컨테이너에 종료를 요청한다크아앙!"),
                ("rm", "종료된 컨테이너의 파일과 남은 자원을 정리한다부우우-"),
            ])
        formatter.write_paragraph()
        formatter.write_text("bukang run --help로 실행 방법을 알려드린다부우우-")


@click.group(cls=BukangGroup, invoke_without_command=True)
@click.help_option("--help", help="부캉이의 사용 안내를 보여드린다부우우-")
@click.pass_context
def main(ctx: click.Context) -> None:
    """하위 명령을 실행하고, 명령이 없으면 도움말을 출력한다"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help(), color=ctx.color)


# rootfs 뒤의 -c, --help 등은 bukang 옵션이 아니라 실행할 명령의 인자로 전달한다
@main.command(
    context_settings={"allow_interspersed_args": False},
    help="압축 해제된 ROOTFS에서 COMMAND를 실행한다크아앙!",
)
@click.argument("rootfs", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
@click.option(
    "--hostname", default="bukang", show_default=True,
    help="컨테이너의 hostname을 정한다부우우-",
)
@click.option(
    "--cgroup-parent", default="/sys/fs/cgroup/bukang", show_default=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="memory controller가 준비된 cgroup v2 부모 경로를 받는다부우우-",
)
@click.help_option("--help", help="실행 방법을 보여드린다부우우-")
@click.pass_context
def run(
    ctx: click.Context,
    rootfs: Path,
    command: tuple[str, ...],
    hostname: str,
    cgroup_parent: Path,
) -> None:
    """입력받은 명령을 runtime에 전달하고 종료 코드를 반환한다"""
    if sys.platform != "linux":
        raise click.ClickException("컨테이너 실행은 Linux에서 가능하다부우우-")

    # Linux 전용 os 상수를 쓰는 runtime은 run 시에만 불러와 다른 OS에서도 help가 열리게 한다
    from bukang.core import runtime

    click.echo("namespace·rootfs·cgroup을 준비해 실행한다크아앙!", err=True)
    try:
        exit_code = runtime.run(
            command=list(command), hostname=hostname, rootfs=rootfs,
            cgroup_parent=cgroup_parent,
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise click.ClickException(f"실행하지 못했다부우우-\n{error}") from error
    # 컨테이너의 종료 결과를 bukang 명령의 종료 코드로 전달한다
    ctx.exit(exit_code)
