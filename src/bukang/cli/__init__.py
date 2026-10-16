"""사용자 입력과 도움말을 담당하는 CLI 계층"""

import shlex
import shutil
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import click

from bukang.core.events import RunEvent

from .image import render_bukang_image


def narrate(event: RunEvent, **details: object) -> None:
    """runtime이 전달한 단계와 값을 짧은 부캉이 안내로 출력한다"""
    # 셸이 이미 실행된 뒤의 안내는 프롬프트와 섞이므로 표시하지 않는다
    if event is RunEvent.STATE_SAVED:
        return
    if event is RunEvent.PREPARING:
        container_id = str(details["container_id"])[:8]
        click.echo(
            f"🦈 {container_id} 실행을 준비한다크아앙!\n"
            f"  rootfs   {details['rootfs']}\n"
            f"  hostname {details['hostname']}\n",
            err=True,
        )
        return
    if event is RunEvent.LIMITS_CONFIGURED:
        memory_mib = cast(int, details["memory_bytes"]) / (1024 * 1024)
        swap_bytes = cast(int, details["swap_bytes"])
        swap = "사용 안 함" if swap_bytes == 0 else f"{swap_bytes / (1024 * 1024):g} MiB"
        message = f"메모리 {memory_mib:g} MiB · swap {swap}으로 설정했다부우우-"
        if details["cpu_quota_us"] is not None:
            quota_ms = cast(int, details["cpu_quota_us"]) / 1000
            period_ms = cast(int, details["cpu_period_us"]) / 1000
            message += f"\n🦈 CPU는 {period_ms:g}ms마다 {quota_ms:g}ms까지 쓰게 했다부우우-"
    else:
        messages = {
            RunEvent.WORKSPACE_READY: "작업 디렉터리를 준비했다부우우-",
            RunEvent.CHILD_CREATED: "새 PID namespace에 자식을 만들었다부우우- [호스트 PID {pid}]",
            RunEvent.CGROUP_READY: "cgroup 등록을 마쳤다부우우-",
            RunEvent.EXITED: "컨테이너가 종료됐다부우우- [종료 코드 {exit_code}]",
            RunEvent.CGROUP_REMOVED: "사용한 cgroup을 정리했다부우우-",
        }
        message = messages[event].format_map(details)
    # 안내는 stderr로 보내 컨테이너 명령의 stdout과 구분한다
    click.echo(f"🦈 {message}", err=True)


class BukangGroup(click.Group):
    """부캉이 그림과 한글 도움말을 표시한다"""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """부캉이의 소개와 사용법, 명령을 안내한다"""
        width = max(1, min(44, shutil.get_terminal_size().columns - 2))
        formatter.write(render_bukang_image(width) + "\n\n")
        formatter.write_text("🦈 컨테이너를 만드는 상어, 부캉이다크아앙!")
        formatter.write_text("🦈 격리된 공간을 만드는 과정을 하나씩 알려드린다부우우-")
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
                ("run", "🦈 컨테이너를 실행하고, 끝날 때까지 기다린다부우우-"),
                ("run -d", "🦈 컨테이너를 백그라운드로 실행한다크아앙!"),
                ("ps", "🦈 저장된 컨테이너와 현재 실행 여부를 보여드린다부우우-"),
                ("rm", "🦈 종료된 컨테이너의 파일과 남은 자원을 정리한다부우우-"),
            ])
        formatter.write_paragraph()
        formatter.write_text("🦈 bukang run --help로 실행 방법을 알려드린다부우우-")


@click.group(cls=BukangGroup, invoke_without_command=True)
@click.help_option("--help", help="🦈 부캉이의 사용 안내를 보여드린다부우우-")
@click.pass_context
def main(ctx: click.Context) -> None:
    """하위 명령을 실행하고, 명령이 없으면 도움말을 출력한다"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help(), color=ctx.color)


# rootfs 뒤의 -c, --help 등은 bukang 옵션이 아니라 실행할 명령의 인자로 전달한다
@main.command(
    context_settings={"allow_interspersed_args": False},
    help="🦈 압축 해제된 ROOTFS에서 COMMAND를 실행한다크아앙!",
)
@click.argument("rootfs", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
@click.option(
    "-d", "--detach", is_flag=True,
    help="🦈 출력을 로그에 저장하고 백그라운드로 실행한다부우우-",
)
@click.option(
    "--hostname", default="bukang", show_default=True,
    help="🦈 컨테이너의 hostname을 정한다부우우-",
)
@click.option(
    "--cgroup-parent", default="/sys/fs/cgroup/bukang", show_default=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="🦈 memory controller가 준비된 cgroup v2 부모 경로를 받는다부우우-",
)
@click.help_option("--help", help="🦈 실행 방법을 보여드린다부우우-")
@click.pass_context
def run(
    ctx: click.Context,
    rootfs: Path,
    command: tuple[str, ...],
    hostname: str,
    cgroup_parent: Path,
    detach: bool,
) -> None:
    """입력받은 명령을 runtime에 전달하고 종료 코드를 반환한다"""
    if sys.platform != "linux":
        raise click.ClickException("🦈 컨테이너 실행은 Linux에서 가능하다부우우-")

    # Linux 전용 os 상수를 쓰는 runtime은 run 시에만 불러와 다른 OS에서도 help가 열리게 한다
    from bukang.core import runtime

    try:
        result = runtime.run(
            command=list(command), hostname=hostname, rootfs=rootfs,
            cgroup_parent=cgroup_parent,
            event_callback=narrate,
            detach=detach,
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise click.ClickException(f"🦈 실행하지 못했다부우우-\n{error}") from error
    if isinstance(result, str):
        click.echo("🦈 백그라운드 실행을 시작했다부우우-", err=True)
        # UUID만 stdout에 출력해 셸 변수로 받을 수 있게 한다
        click.echo(result)
        return
    # foreground에서는 컨테이너의 종료 결과를 CLI 종료 코드로 전달한다
    ctx.exit(result)


@main.command(help="🦈 저장된 컨테이너와 현재 실행 여부를 보여드린다부우우-")
@click.help_option("--help", help="🦈 목록 조회 방법을 보여드린다부우우-")
def ps() -> None:
    """저장된 컨테이너의 UUID, PID, 실행 여부와 명령을 출력한다"""
    if sys.platform != "linux":
        raise click.ClickException("🦈 실행 상태 조회는 Linux에서 가능하다부우우-")

    from bukang.core import runtime

    try:
        containers = runtime.list_containers()
    except (OSError, ValueError, TypeError) as error:
        # 권한 문제나 잘못된 상태 파일을 빈 목록 또는 종료 상태로 숨기지 않는다
        raise click.ClickException(f"🦈 목록을 읽지 못했다부우우-\n{error}") from error
    if not containers:
        click.echo("🦈 저장된 컨테이너가 없다부우우-")
        return

    click.echo("🦈 저장된 컨테이너의 현재 상태를 보여드린다부우우-", err=True)
    click.echo(f"{'UUID':36}  {'PID':>8}  상태     명령")
    for container, running in containers:
        status = "실행 중" if running else "종료   "
        # 종료된 항목의 PID는 재사용될 수 있으므로 현재 PID처럼 표시하지 않는다
        pid = str(container.pid) if running else "-"
        command = shlex.join(container.command).replace("\n", "\\n").replace("\r", "\\r")
        click.echo(f"{container.id:36}  {pid:>8}  {status}  {command}")


@main.command(help="🦈 종료된 컨테이너의 파일과 cgroup을 삭제한다부우우-")
@click.argument("container_id", type=click.UUID)
@click.help_option("--help", help="🦈 컨테이너 삭제 방법을 보여드린다부우우-")
def rm(container_id: UUID) -> None:
    """UUID로 지정한 컨테이너를 삭제하고 결과를 출력한다"""
    if sys.platform != "linux":
        raise click.ClickException("🦈 컨테이너 삭제는 Linux에서 가능하다부우우-")

    from bukang.core import runtime

    try:
        runtime.remove(str(container_id))
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        raise click.ClickException(f"🦈 삭제하지 못했다부우우-\n{error}") from error
    click.echo(f"🦈 컨테이너 {str(container_id)[:8]}를 삭제했다부우우-")
