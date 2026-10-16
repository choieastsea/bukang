"""namespace·rootfs·cgroup을 준비하고 명령을 실행하는 흐름"""

import os
import shutil
import signal
from pathlib import Path
from uuid import uuid4

from bukang.core import state
from bukang.linux import cgroup, filesystem, namespace, process
from bukang.linux.namespace import Namespace


def _exec_child(
    command: list[str],
    hostname: str,
    rootfs: Path,
    workspace: Path,
    ready_fd: int,
    error_fd: int,
    parent_fds: tuple[int, ...],
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
    memory_bytes: int = 50 * 1024 * 1024,
    cpu_quota_us: int | None = None,
) -> int:
    """컨테이너를 실행하고 종료 코드를 반환한다

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
        cgroup.create(cgroup_path)
        group_created = True
        cgroup.set_memory(cgroup_path, memory_bytes)
        if cpu_quota_us is not None:
            cgroup.set_cpu(cgroup_path, cpu_quota_us)

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
                )
        finally:
            # 자식은 exec 또는 _exit로 끝난다 이 부분은 부모가 수행한다
            namespace.setns(original_pid_fd, Namespace.PID)

        # 부모는 오류를 읽는 쪽과 준비 완료를 쓰는 쪽만 남긴다
        for fd in (original_pid_fd, error_write, ready_read):
            os.close(fd)
            fds.remove(fd)
        cgroup.add_process(cgroup_path, pid)
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

        # 초기화 오류가 보고되지 않았을 때 저장하고, foreground 실행이 끝날 때까지 기다린다
        state.save(container)
        saved_state = container
        _, status = os.waitpid(pid, 0)
        pid = None
        completed = True
        exit_code = os.waitstatus_to_exitcode(status)
        # 시그널 종료는 -시그널 번호로 나오므로 셸 관례인 128 + 시그널 번호로 바꾼다
        return exit_code if exit_code >= 0 else 128 - exit_code
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
            if group_created:
                cgroup.remove(cgroup_path)
        finally:
            # 자식 종료로 mount namespace와 마운트가 사라진 뒤 실패한 실행의 파일을 지운다
            # 끝까지 실행한 컨테이너의 상태와 변경 파일은 나중에 rm으로 지울 수 있게 남긴다
            if not completed:
                shutil.rmtree(workspace)
                if saved_state is not None:
                    state.delete(saved_state.id)
