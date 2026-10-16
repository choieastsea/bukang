"""namespace·rootfs·cgroup을 준비하고 명령을 실행하는 흐름"""

import os
import shutil
import signal
from pathlib import Path
from uuid import uuid4

from bukang.core import state
from bukang.core.events import EventCallback, RunEvent
from bukang.linux import cgroup, filesystem, namespace, process
from bukang.linux.namespace import Namespace


def list_containers() -> list[tuple[state.ContainerState, bool]]:
    """저장된 컨테이너마다 현재 프로세스가 살아 있는지 확인해 반환한다"""
    return [
        (container, process.is_running(
            container.pid, container.start_time, container.boot_id,
        ))
        for container in state.list_states()
    ]


def _exec_child(
    command: list[str],
    hostname: str,
    rootfs: Path,
    workspace: Path,
    ready_fd: int,
    error_fd: int,
    parent_fds: tuple[int, ...],
    detach: bool,
) -> None:
    """부모가 cgroup에 등록할 때까지 기다린 뒤 namespace와 rootfs를 설정하고 명령을 실행한다"""
    try:
        # fork로 복사된 FD 중 부모만 쓰는 것은 닫는다
        for fd in parent_fds:
            os.close(fd)
        # 부모가 제한을 적용하기 전에 컨테이너 명령이 실행되지 않도록 기다린다
        if os.read(ready_fd, 1) != b"1":
            raise RuntimeError("부모가 초기화를 중단했습니다")
        os.close(ready_fd)

        if detach:
            process.detach(workspace / "container.log")

        # PID namespace는 이미 fork 때 적용됐으므로 hostname과 마운트만 분리한다
        namespace.unshare(Namespace.UTS | Namespace.MOUNT)
        namespace.set_hostname(hostname)
        # 이후 마운트 작업이 호스트에 전달되지 않도록 먼저 설정한다
        filesystem.make_private()
        filesystem.mount_overlay(
            rootfs, workspace / "upper", workspace / "work", workspace / "merged"
        )
        # 합쳐진 파일시스템을 /로 바꾼 뒤, 컨테이너 PID를 보여주는 /proc을 붙인다
        filesystem.pivot_root(workspace / "merged")
        filesystem.mount_proc()
        # 새 프로세스를 만드는 것이 아니라 현재 자식의 프로그램을 교체한다
        os.execvp(command[0], command)
    except BaseException as error:
        message = f"{type(error).__name__}: {error}".encode()
        os.write(error_fd, message[:4096])
    finally:
        # exec 성공 시에는 여기로 돌아오지 않는다 실패 시 부모 코드를 실행하지 않고 종료한다
        os._exit(1)


def run(
    command: list[str],
    hostname: str,
    rootfs: Path,
    cgroup_parent: Path,
    event_callback: EventCallback,
    memory_bytes: int = 50 * 1024 * 1024,
    cpu_quota_us: int | None = None,
    detach: bool = False,
) -> int | str:
    """컨테이너를 실행하고 종료 코드 또는 백그라운드 컨테이너의 UUID를 반환한다

    진행 단계와 관련 값은 부모에서 event_callback로 전달한다
    종료 후에도 state.json과 컨테이너에서 변경한 파일은 삭제하지 않는다
    """
    if not command:
        raise ValueError("실행할 명령이 필요합니다")
    # 상태 파일, 작업 디렉터리, cgroup에 같은 UUID를 사용한다
    container_id = str(uuid4())
    rootfs = rootfs.resolve(strict=True)
    workspace = (state.STATE_ROOT.parent / "workspaces" / container_id).resolve()
    cgroup_path = cgroup_parent.resolve(strict=True) / container_id
    if not rootfs.is_dir():
        raise ValueError("rootfs는 디렉터리여야 합니다")
    if workspace.is_relative_to(rootfs) or rootfs.is_relative_to(workspace):
        raise ValueError("rootfs와 실행 디렉터리는 서로 포함될 수 없습니다")

    # 출력 문구는 CLI가 정한다 자식에는 콜백을 전달하지 않는다
    event_callback(
        RunEvent.PREPARING,
        container_id=container_id, rootfs=rootfs, hostname=hostname,
    )
    # 중간에 실패해도 실제로 만든 자원만 정리하기 위해 기록한다
    pid = None
    fds = []
    group_created = False
    completed = False
    saved_state = None
    workspace.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    workspace.mkdir(mode=0o700)
    try:
        # upper: 변경 파일, work: OverlayFS 내부 작업, merged: 합쳐진 파일을 볼 경로
        for name in ("upper", "work", "merged"):
            (workspace / name).mkdir()
        event_callback(RunEvent.WORKSPACE_READY, workspace=workspace)
        cgroup.create(cgroup_path)
        group_created = True
        cgroup.set_memory(cgroup_path, memory_bytes)
        if cpu_quota_us is not None:
            cgroup.set_cpu(cgroup_path, cpu_quota_us)
        event_callback(
            RunEvent.LIMITS_CONFIGURED,
            memory_bytes=memory_bytes, swap_bytes=0,
            cpu_quota_us=cpu_quota_us, cpu_period_us=100_000,
        )

        # fork 후 부모의 '다음 자식이 들어갈 PID namespace'를 되돌릴 때 사용한다
        original_pid_fd = os.open("/proc/self/ns/pid", os.O_RDONLY)
        fds.append(original_pid_fd)
        # error: 자식 → 부모 오류 전달, ready: 부모 → 자식 준비 완료 전달
        error_read, error_write = os.pipe()
        fds.extend((error_read, error_write))
        ready_read, ready_write = os.pipe()
        fds.extend((ready_read, ready_write))

        # 부모의 PID는 그대로이고, 다음 fork로 생기는 자식이 새 namespace의 PID 1이 된다
        namespace.unshare(Namespace.PID)
        try:
            pid = os.fork()
            if pid == 0:
                _exec_child(
                    command, hostname, rootfs, workspace, ready_read, error_write,
                    (original_pid_fd, error_read, ready_write),
                    detach,
                )
        finally:
            # 자식은 exec 또는 _exit로 끝난다 이 부분은 부모가 수행한다
            namespace.setns(original_pid_fd, Namespace.PID)

        event_callback(RunEvent.CHILD_CREATED, pid=pid)
        # 부모는 오류를 읽는 쪽과 준비 완료를 쓰는 쪽만 남긴다
        for fd in (original_pid_fd, error_write, ready_read):
            os.close(fd)
            fds.remove(fd)
        cgroup.add_process(cgroup_path, pid)
        event_callback(RunEvent.CGROUP_READY, pid=pid, cgroup_path=cgroup_path)
        # 자식이 기다리는 동안 식별 정보를 읽는다 PID 재사용은 시작 시점과 부팅 ID로 구분한다
        container = state.ContainerState(
            id=container_id,
            command=command,
            pid=pid,
            start_time=process.get_start_time(pid),
            boot_id=process.get_boot_id(),
            workspace=str(workspace),
            cgroup_path=str(cgroup_path),
        )
        # cgroup 등록과 정보 수집이 끝났으므로 자식이 초기화를 계속하도록 알린다
        os.write(ready_write, b"1")
        os.close(ready_write)
        fds.remove(ready_write)

        # Python이 만든 파이프 FD는 exec 시 닫힌다 오류 메시지가 없으면 빈 바이트(EOF)를 받는다
        error = os.read(error_read, 4096)
        if error:
            raise RuntimeError(error.decode(errors="replace"))

        # 초기화 오류가 보고되지 않았을 때 저장한다 foreground일 때만 종료를 기다린다
        state.save(container)
        saved_state = container
        event_callback(
            RunEvent.STATE_SAVED,
            state_path=state.STATE_ROOT / container_id / "state.json",
        )
        if detach:
            # 초기화 확인과 상태 저장이 끝났으므로 자식을 기다리지 않고 부모를 종료한다
            completed = True
            return container_id
        _, status = os.waitpid(pid, 0)
        pid = None
        completed = True
        exit_code = os.waitstatus_to_exitcode(status)
        # 시그널 종료는 -시그널 번호로 나오므로 셸 관례인 128 + 시그널 번호로 바꾼다
        exit_code = exit_code if exit_code >= 0 else 128 - exit_code
        event_callback(RunEvent.EXITED, exit_code=exit_code)
        return exit_code
    except BaseException:
        # 부모 작업이 실패하면 자식을 종료시키고 waitpid로 종료 결과를 회수한다
        if pid is not None and pid > 0:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        raise
    finally:
        for fd in fds:
            os.close(fd)
        try:
            # 백그라운드 실행에 성공했다면 자식이 계속 사용할 cgroup을 남긴다
            if group_created and not (detach and completed):
                cgroup.remove(cgroup_path)
                event_callback(RunEvent.CGROUP_REMOVED, cgroup_path=cgroup_path)
        finally:
            # 실패 시 자식 종료로 마운트가 사라진 뒤 파일을 지운다
            # 실행에 성공한 컨테이너의 상태와 변경 파일은 이후 rm을 위해 남긴다
            if not completed:
                shutil.rmtree(workspace)
                if saved_state is not None:
                    state.delete(saved_state.id)
