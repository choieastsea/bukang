"""OverlayFS 마운트와 컨테이너의 / 경로 변경"""

import ctypes
import os
from functools import cache
from pathlib import Path

MS_REC = 16384
MS_PRIVATE = 1 << 18
MNT_DETACH = 2


@cache
def _libc() -> ctypes.CDLL:
    """mount, umount2, pivot_root를 호출할 C 라이브러리를 불러온다"""
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    # Python 값을 C 함수에 전달할 수 있도록 인자와 반환값의 타입을 지정한다
    libc.mount.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
        ctypes.c_ulong, ctypes.c_char_p,
    ]
    libc.mount.restype = ctypes.c_int
    libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
    libc.umount2.restype = ctypes.c_int
    libc.syscall.restype = ctypes.c_long
    return libc


def _check(result: int, target: str) -> None:
    """호출 결과가 -1이면 Linux 오류 번호와 메시지로 OSError를 발생시킨다"""
    if result == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


def make_private() -> None:
    """이 namespace의 마운트와 해제가 다른 namespace에 영향을 주지 않게 한다"""
    # MS_REC를 함께 지정해 / 아래의 기존 마운트에도 PRIVATE 설정을 적용한다
    _check(_libc().mount(None, b"/", None, MS_REC | MS_PRIVATE, None), "/")


def mount_overlay(lower: Path, upper: Path, work: Path, merged: Path) -> None:
    """원본 lower와 변경 파일을 담는 upper를 합쳐 merged에 마운트한다

    work는 OverlayFS가 내부 작업에 사용하는 빈 디렉터리다
    """
    paths = [path.resolve(strict=True) for path in (lower, upper, work, merged)]
    # 경로 문자가 OverlayFS 옵션 구분자나 이스케이프로 해석되는 것을 막는다
    if any(any(char in str(path) for char in ",:\\") for path in paths):
        raise ValueError("OverlayFS 경로에는 쉼표·콜론·역슬래시를 사용할 수 없습니다")
    lower, upper, work, merged = paths
    options = f"lowerdir={lower},upperdir={upper},workdir={work}"
    _check(
        _libc().mount(b"overlay", os.fsencode(merged), b"overlay", 0, os.fsencode(options)),
        str(merged),
    )


def unmount(target: Path, lazy: bool = False) -> None:
    """target의 마운트를 해제한다

    lazy=True이면 경로에서 먼저 떼어내고, 사용이 끝나면 실제로 해제한다
    """
    _check(_libc().umount2(os.fsencode(target), MNT_DETACH if lazy else 0), str(target))


def pivot_root(root: Path) -> None:
    """root를 새로운 /로 바꾸고 기존 /의 마운트를 해제한다"""
    # pivot_root는 syscall로 직접 호출하며 CPU 아키텍처마다 호출 번호가 다르다
    syscall_number = {"x86_64": 155, "aarch64": 41}.get(os.uname().machine)
    if syscall_number is None:
        raise NotImplementedError("pivot_root는 x86_64·aarch64에서 지원합니다")
    # /를 바꾼 뒤에는 호스트 라이브러리 경로에 접근할 수 없으므로 먼저 불러온다
    libc = _libc()
    os.chdir(root)
    # pivot_root가 기존 /를 잠시 옮겨 둘 위치이며, 전환 후에는 /put_old가 된다
    os.mkdir("put_old")
    _check(
        libc.syscall(ctypes.c_long(syscall_number), ctypes.c_char_p(b"."),
                     ctypes.c_char_p(b"put_old")),
        str(root),
    )
    # 작업 디렉터리도 새 /로 옮기고 이전 파일시스템을 떼어낸다
    os.chdir("/")
    unmount(Path("/put_old"), lazy=True)
    os.rmdir("/put_old")


def mount_proc() -> None:
    """현재 PID namespace의 프로세스 정보를 볼 수 있도록 /proc을 마운트한다"""
    os.makedirs("/proc", exist_ok=True)
    _check(_libc().mount(b"proc", b"/proc", b"proc", 0, None), "/proc")
