"""Linux 프로세스 식별 정보 조회"""

from pathlib import Path


def _read_stat(pid: int) -> list[str]:
    stat = Path(f"/proc/{pid}/stat").read_text()
    # 이름에는 공백과 괄호가 들어갈 수 있어 마지막 ) 뒤에서 필드를 나눈다
    return stat.rsplit(")", 1)[1].split()


def get_start_time(pid: int) -> int:
    """부팅부터 프로세스 시작까지 지난 시간을 커널의 시간 단위인 tick으로 읽는다"""
    fields = _read_stat(pid)
    # 세 번째 필드부터 남았으므로 22번째 필드인 starttime의 인덱스는 19다
    return int(fields[19])


def get_boot_id() -> str:
    """호스트가 부팅할 때마다 새로 정해지는 ID를 읽는다"""
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def is_running(pid: int, start_time: int, boot_id: str) -> bool:
    """저장한 PID가 같은 프로세스이고 아직 종료되지 않았는지 확인한다"""
    if get_boot_id() != boot_id:
        return False
    try:
        fields = _read_stat(pid)
    except (FileNotFoundError, ProcessLookupError):
        # 조회 도중 프로세스가 사라진 경우도 종료로 처리한다
        return False
    # 상태와 시작 시점은 한 번 읽은 stat에서 확인한다 Z는 zombie, X/x는 종료 상태다
    return int(fields[19]) == start_time and fields[0] not in {"Z", "X", "x"}
