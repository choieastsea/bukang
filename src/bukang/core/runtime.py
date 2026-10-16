"""namespace·rootfs·cgroup을 준비하고 명령을 실행하는 흐름"""

import os
import shutil
import signal
from pathlib import Path

from bukang.linux import cgroup, filesystem, namespace
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
    """부모의 등록 완료를 기다린 뒤 격리 환경에서 명령을 실행한다"""
    try:
        for fd in parent_fds:
            os.close(fd)
        if os.read(ready_fd, 1) != b"1":
            raise RuntimeError("부모가 초기화를 중단했습니다")
        os.close(ready_fd)

        namespace.unshare(Namespace.UTS | Namespace.MOUNT)
        namespace.set_hostname(hostname)
        filesystem.make_private()
        filesystem.mount_overlay(
            rootfs, workspace / "upper", workspace / "work", workspace / "merged"
        )
        filesystem.pivot_root(workspace / "merged")
        filesystem.mount_proc()
        os.execvp(command[0], command)
    except BaseException as error:
        message = f"{type(error).__name__}: {error}".encode()
        os.write(error_fd, message[:4096])
    finally:
        os._exit(1)


def run(
    command: list[str],
    hostname: str,
    rootfs: Path,
    workspace: Path,
    cgroup_path: Path,
    memory_bytes: int = 50 * 1024 * 1024,
    cpu_quota_us: int | None = None,
) -> int:
    """rootfs와 자원 제한을 적용해 실행하고 종료 후 쓰기 영역은 보존한다"""
    if not command:
        raise ValueError("실행할 명령이 필요합니다")
    rootfs = rootfs.resolve(strict=True)
    workspace = workspace.resolve()
    cgroup_path = cgroup_path.resolve()
    if not rootfs.is_dir():
        raise ValueError("rootfs는 디렉터리여야 합니다")
    if workspace.is_relative_to(rootfs) or rootfs.is_relative_to(workspace):
        raise ValueError("rootfs와 실행 디렉터리는 서로 포함될 수 없습니다")

    pid = None
    fds = []
    group_created = False
    completed = False
    workspace.mkdir()
    try:
        for name in ("upper", "work", "merged"):
            (workspace / name).mkdir()
        cgroup.create(cgroup_path)
        group_created = True
        cgroup.set_memory(cgroup_path, memory_bytes)
        if cpu_quota_us is not None:
            cgroup.set_cpu(cgroup_path, cpu_quota_us)

        original_pid_fd = os.open("/proc/self/ns/pid", os.O_RDONLY)
        fds.append(original_pid_fd)
        error_read, error_write = os.pipe()
        fds.extend((error_read, error_write))
        ready_read, ready_write = os.pipe()
        fds.extend((ready_read, ready_write))

        namespace.unshare(Namespace.PID)
        try:
            pid = os.fork()
            if pid == 0:
                _exec_child(
                    command, hostname, rootfs, workspace, ready_read, error_write,
                    (original_pid_fd, error_read, ready_write),
                )
        finally:
            namespace.setns(original_pid_fd, Namespace.PID)

        for fd in (original_pid_fd, error_write, ready_read):
            os.close(fd)
            fds.remove(fd)
        cgroup.add_process(cgroup_path, pid)
        os.write(ready_write, b"1")
        os.close(ready_write)
        fds.remove(ready_write)

        # exec 성공 시 상속되지 않는 파이프가 닫혀 EOF를 받는다
        error = os.read(error_read, 4096)
        _, status = os.waitpid(pid, 0)
        pid = None
        if error:
            raise RuntimeError(error.decode(errors="replace"))

        completed = True
        exit_code = os.waitstatus_to_exitcode(status)
        return exit_code if exit_code >= 0 else 128 - exit_code
    except BaseException:
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
            # 자식 종료로 전용 mount namespace가 사라진 뒤 디렉터리를 정리한다
            if not completed:
                shutil.rmtree(workspace)
