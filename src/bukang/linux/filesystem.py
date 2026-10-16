"""OverlayFS와 루트 파일시스템 전환"""

import ctypes
import os
from functools import cache
from pathlib import Path

MS_REC = 16384
MS_PRIVATE = 1 << 18
MNT_DETACH = 2


@cache
def _libc() -> ctypes.CDLL:
    """마운트와 시스템 호출에 사용할 libc를 불러온다"""
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
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
    """실패한 Linux 호출의 errno를 OSError로 전달한다"""
    if result == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


def make_private() -> None:
    """현재 mount namespace의 마운트 변경 전파를 차단한다"""
    _check(_libc().mount(None, b"/", None, MS_REC | MS_PRIVATE, None), "/")


def mount_overlay(lower: Path, upper: Path, work: Path, merged: Path) -> None:
    """준비된 원본과 쓰기 영역을 OverlayFS로 마운트한다"""
    paths = [path.resolve(strict=True) for path in (lower, upper, work, merged)]
    if any(any(char in str(path) for char in ",:\\") for path in paths):
        raise ValueError("OverlayFS 경로에는 쉼표·콜론·역슬래시를 사용할 수 없습니다")
    lower, upper, work, merged = paths
    options = f"lowerdir={lower},upperdir={upper},workdir={work}"
    _check(
        _libc().mount(b"overlay", os.fsencode(merged), b"overlay", 0, os.fsencode(options)),
        str(merged),
    )


def unmount(target: Path, lazy: bool = False) -> None:
    """마운트를 해제하며 lazy이면 참조가 남아 있어도 경로에서 분리한다"""
    _check(_libc().umount2(os.fsencode(target), MNT_DETACH if lazy else 0), str(target))


def pivot_root(root: Path) -> None:
    """새 마운트로 루트를 교체하고 이전 루트를 분리한다"""
    syscall_number = {"x86_64": 155, "aarch64": 41}.get(os.uname().machine)
    if syscall_number is None:
        raise NotImplementedError("pivot_root는 x86_64·aarch64에서 지원합니다")
    libc = _libc()
    os.chdir(root)
    os.mkdir("put_old")
    _check(
        libc.syscall(ctypes.c_long(syscall_number), ctypes.c_char_p(b"."),
                     ctypes.c_char_p(b"put_old")),
        str(root),
    )
    os.chdir("/")
    unmount(Path("/put_old"), lazy=True)
    os.rmdir("/put_old")


def mount_proc() -> None:
    """현재 PID namespace 기준의 procfs를 새 루트에 마운트한다"""
    os.makedirs("/proc", exist_ok=True)
    _check(_libc().mount(b"proc", b"/proc", b"proc", 0, None), "/proc")
