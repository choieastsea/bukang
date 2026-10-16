"""Linux 프로세스 식별 정보 조회"""

from pathlib import Path


def get_start_time(pid: int) -> int:
    """부팅부터 프로세스 시작까지 지난 시간을 커널의 시간 단위인 tick으로 읽는다"""
    stat = Path(f"/proc/{pid}/stat").read_text()
    # 이름에는 공백과 괄호가 들어갈 수 있어 마지막 ) 뒤에서 필드를 나눈다
    fields = stat.rsplit(")", 1)[1].split()
    # 세 번째 필드부터 남았으므로 22번째 필드인 starttime의 인덱스는 19다
    return int(fields[19])


def get_boot_id() -> str:
    """호스트가 부팅할 때마다 새로 정해지는 ID를 읽는다"""
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
