"""UUID로 식별하는 컨테이너 상태 저장과 조회"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

STATE_ROOT = Path("/var/lib/bukang/containers")


@dataclass
class ContainerState:
    """컨테이너 조회와 자원 정리에 필요한 정보"""

    command: list[str]
    pid: int
    start_time: int
    boot_id: str
    workspace: str
    cgroup_path: str
    id: str = field(default_factory=lambda: str(uuid4()))


def _directory(container_id: str) -> Path:
    return STATE_ROOT / str(UUID(container_id))


def save(state: ContainerState) -> None:
    """상태를 JSON으로 저장하고 기존 파일은 한 번에 교체한다"""
    directory = _directory(state.id)
    created = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        file = NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False
        )
        temporary = Path(file.name)
        try:
            with file:
                json.dump(asdict(state), file, ensure_ascii=False, indent=2)
            temporary.replace(directory / "state.json")
        finally:
            temporary.unlink(missing_ok=True)
    except BaseException:
        if created:
            directory.rmdir()
        raise


def load(container_id: str) -> ContainerState:
    """UUID에 해당하는 컨테이너 상태를 읽는다"""
    path = _directory(container_id) / "state.json"
    return ContainerState(**json.loads(path.read_text(encoding="utf-8")))


def list_states() -> list[ContainerState]:
    """저장된 컨테이너 상태를 모두 읽는다"""
    return [load(path.parent.name) for path in sorted(STATE_ROOT.glob("*/state.json"))]


def delete(container_id: str) -> None:
    """컨테이너 자원 정리 후 저장된 상태를 삭제한다"""
    directory = _directory(container_id)
    (directory / "state.json").unlink()
    directory.rmdir()
