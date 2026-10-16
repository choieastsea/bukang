"""Linux 프로세스 식별 정보 조회"""

from pathlib import Path


def get_start_time(pid: int) -> int:
    """부팅 후 프로세스가 시작된 시점을 clock tick 단위로 읽는다"""
    stat = Path(f"/proc/{pid}/stat").read_text()
    # 괄호 안의 프로세스 이름을 제외하면 세 번째 필드부터 시작한다
    fields = stat.rsplit(")", 1)[1].split()
    return int(fields[19])


def get_boot_id() -> str:
    """현재 호스트의 부팅 ID를 읽는다"""
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
