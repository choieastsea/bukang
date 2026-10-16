"""UUID로 식별하는 컨테이너 상태 저장과 조회"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

STATE_ROOT = Path("/var/lib/bukang/containers")


@dataclass
class ContainerState:
    """컨테이너의 UUID, 실행 명령, 프로세스 정보와 파일 경로"""

    command: list[str]
    pid: int
    # PID는 재사용되므로 같은 부팅에서 같은 시점에 시작한 프로세스인지 함께 확인한다
    start_time: int
    boot_id: str
    workspace: str
    cgroup_path: str
    id: str = field(default_factory=lambda: str(uuid4()))


def _directory(container_id: str) -> Path:
    # 임의 경로가 아니라 UUID 형식의 디렉터리 이름만 받는다
    return STATE_ROOT / str(UUID(container_id))


def save(state: ContainerState) -> None:
    """컨테이너 정보를 임시 파일에 쓴 뒤 state.json으로 교체한다"""
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
            # 쓰기가 끝난 파일로 교체해 다른 CLI가 작성 중인 JSON을 읽지 않게 한다
            temporary.replace(directory / "state.json")
        finally:
            temporary.unlink(missing_ok=True)
    except BaseException:
        # 이번 저장에서 만든 빈 디렉터리만 지우고, 기존 상태 디렉터리는 남긴다
        if created:
            directory.rmdir()
        raise


def load(container_id: str) -> ContainerState:
    """UUID에 해당하는 state.json을 읽어 ContainerState로 반환한다"""
    path = _directory(container_id) / "state.json"
    return ContainerState(**json.loads(path.read_text(encoding="utf-8")))


def list_states() -> list[ContainerState]:
    """저장된 state.json을 모두 읽어 컨테이너 목록을 반환한다"""
    return [load(path.parent.name) for path in sorted(STATE_ROOT.glob("*/state.json"))]


def delete(container_id: str) -> None:
    """state.json과 이를 담은 디렉터리를 삭제한다"""
    directory = _directory(container_id)
    (directory / "state.json").unlink()
    directory.rmdir()
