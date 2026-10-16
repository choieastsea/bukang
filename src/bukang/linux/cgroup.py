"""cgroup v2의 자원 제한과 프로세스 등록"""

from pathlib import Path


def create(path: Path) -> None:
    """path에 새 cgroup을 만든다 부모 cgroup은 이미 있어야 한다"""
    if not (path.parent / "cgroup.controllers").is_file():
        raise ValueError("부모 경로가 cgroup v2 계층이 아닙니다")
    # cgroup 파일시스템에서는 디렉터리를 만들면 커널이 제어 파일들을 제공한다
    path.mkdir()


def _write(path: Path, value: str) -> None:
    """memory.max 같은 기존 cgroup 설정 파일에 값을 쓴다"""
    # 없는 제어 파일을 일반 파일로 만들지 않도록, 기존 파일만 여는 r+를 사용한다
    with path.open("r+") as control:
        control.write(value)


def set_memory(path: Path, memory_bytes: int, swap_bytes: int = 0) -> None:
    """cgroup의 메모리와 swap 최대 사용량을 바이트 단위로 설정한다"""
    if memory_bytes <= 0 or swap_bytes < 0:
        raise ValueError("메모리는 양수, swap은 0 이상이어야 합니다")
    _write(path / "memory.max", str(memory_bytes))
    _write(path / "memory.swap.max", str(swap_bytes))


def set_cpu(path: Path, quota_us: int, period_us: int = 100_000) -> None:
    """period_us마다 cgroup이 CPU를 쓸 수 있는 시간을 quota_us로 제한한다

    두 값의 단위는 마이크로초다
    """
    if quota_us <= 0 or period_us <= 0:
        raise ValueError("CPU 할당 시간과 주기는 양수여야 합니다")
    # 예: 50000 100000은 100ms마다 CPU 사용 시간을 50ms까지 허용한다
    _write(path / "cpu.max", f"{quota_us} {period_us}")


def add_process(path: Path, pid: int) -> None:
    """호스트에서 보이는 PID를 cgroup.procs에 써서 cgroup에 넣는다"""
    if pid <= 0:
        raise ValueError("PID는 양수여야 합니다")
    _write(path / "cgroup.procs", str(pid))


def remove(path: Path) -> None:
    """빈 cgroup 디렉터리를 삭제한다"""
    path.rmdir()
