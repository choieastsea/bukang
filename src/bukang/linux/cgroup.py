"""cgroup v2의 자원 제한과 프로세스 등록"""

from pathlib import Path


def create(path: Path) -> None:
    """기존 cgroup v2 계층 아래에 전용 그룹을 만든다"""
    if not (path.parent / "cgroup.controllers").is_file():
        raise ValueError("부모 경로가 cgroup v2 계층이 아닙니다")
    path.mkdir()


def _write(path: Path, value: str) -> None:
    """기존 cgroup 제어 파일에 값을 기록한다"""
    with path.open("r+") as control:
        control.write(value)


def set_memory(path: Path, memory_bytes: int, swap_bytes: int = 0) -> None:
    """메모리와 swap 사용량의 상한을 바이트 단위로 설정한다"""
    if memory_bytes <= 0 or swap_bytes < 0:
        raise ValueError("메모리는 양수, swap은 0 이상이어야 합니다")
    _write(path / "memory.max", str(memory_bytes))
    _write(path / "memory.swap.max", str(swap_bytes))


def set_cpu(path: Path, quota_us: int, period_us: int = 100_000) -> None:
    """주기당 사용할 수 있는 CPU 시간을 마이크로초 단위로 제한한다"""
    if quota_us <= 0 or period_us <= 0:
        raise ValueError("CPU 할당 시간과 주기는 양수여야 합니다")
    _write(path / "cpu.max", f"{quota_us} {period_us}")


def add_process(path: Path, pid: int) -> None:
    """호스트 PID로 프로세스를 그룹에 등록한다"""
    if pid <= 0:
        raise ValueError("PID는 양수여야 합니다")
    _write(path / "cgroup.procs", str(pid))


def remove(path: Path) -> None:
    """프로세스가 남아 있지 않은 전용 그룹을 삭제한다"""
    path.rmdir()
