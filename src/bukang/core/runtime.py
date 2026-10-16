"""PID·UTS namespace에서 명령을 실행하는 흐름"""

import os
import signal

from bukang.linux import namespace


def _exec_child(command: list[str], hostname: str, error_fd: int) -> None:
    """자식의 hostname을 분리하고 명령으로 교체하며 실패는 부모에 전달한다"""
    try:
        namespace.unshare(os.CLONE_NEWUTS)
        namespace.set_hostname(hostname)
        os.execvp(command[0], command)
    except BaseException as error:
        message = f"{type(error).__name__}: {error}".encode()
        os.write(error_fd, message[:4096])
    finally:
        os._exit(1)


def run(command: list[str], hostname: str) -> int:
    """PID·UTS namespace에서 명령을 실행하고 종료 코드를 반환한다"""
    if not command:
        raise ValueError("실행할 명령이 필요합니다")

    pid = None
    with open("/proc/self/ns/pid", "rb") as original_pid_ns:
        error_read, error_write = os.pipe()
        try:
            namespace.unshare(os.CLONE_NEWPID)
            try:
                pid = os.fork()
                if pid == 0:
                    os.close(error_read)
                    original_pid_ns.close()
                    _exec_child(command, hostname, error_write)
            finally:
                namespace.setns(original_pid_ns.fileno(), os.CLONE_NEWPID)

            os.close(error_write)
            error_write = None
            # exec 성공 시 상속되지 않는 파이프가 닫혀 EOF를 받는다
            error = os.read(error_read, 4096)
            _, status = os.waitpid(pid, 0)
            pid = None
            if error:
                raise RuntimeError(error.decode(errors="replace"))

            exit_code = os.waitstatus_to_exitcode(status)
            return exit_code if exit_code >= 0 else 128 - exit_code
        except BaseException:
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            raise
        finally:
            os.close(error_read)
            if error_write is not None:
                os.close(error_write)
