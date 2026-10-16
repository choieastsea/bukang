"""Linux namespace 생성·진입과 hostname 설정"""

import os
import socket


def unshare(flags: int) -> None:
    """지정한 namespace를 분리한다. PID namespace는 이후 생성할 자식에 적용된다"""
    os.unshare(flags)


def setns(fd: int, nstype: int = 0) -> None:
    """FD가 가리키는 namespace에 진입한다. PID는 이후 생성할 자식에 적용된다"""
    os.setns(fd, nstype)


def set_hostname(name: str) -> None:
    """현재 UTS namespace의 hostname을 설정한다"""
    socket.sethostname(name)
