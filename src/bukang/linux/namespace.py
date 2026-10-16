"""Linux namespace 생성·진입과 hostname 설정"""

import os
import socket
from enum import IntFlag


class Namespace(IntFlag):
    """PID, mount, UTS 등 namespace 종류를 나타내는 플래그"""

    # IntFlag이므로 MOUNT | UTS처럼 여러 종류를 한 번의 unshare에 전달할 수 있다
    PID = os.CLONE_NEWPID
    MOUNT = os.CLONE_NEWNS
    UTS = os.CLONE_NEWUTS
    IPC = os.CLONE_NEWIPC
    NETWORK = os.CLONE_NEWNET


def unshare(flags: Namespace) -> None:
    """선택한 종류의 namespace를 새로 만들어 현재 프로세스에 적용한다

    PID namespace는 현재 프로세스 대신 이후 fork할 자식에 적용된다
    """
    os.unshare(flags)


def setns(fd: int, nstype: Namespace) -> None:
    """열어 둔 namespace 파일의 fd로 기존 namespace에 들어간다

    nstype은 namespace 종류이며, PID는 이후 fork할 자식에 적용된다
    """
    os.setns(fd, nstype)


def set_hostname(name: str) -> None:
    """현재 UTS namespace의 hostname을 설정한다"""
    socket.sethostname(name)
