"""컨테이너 실행 중 CLI에 알릴 단계"""

from enum import Enum, auto
from typing import Protocol


class RunEvent(Enum):
    """부모 프로세스에서 알리는 실행 단계"""

    PREPARING = auto()
    WORKSPACE_READY = auto()
    LIMITS_CONFIGURED = auto()
    CHILD_CREATED = auto()
    CGROUP_READY = auto()
    STATE_SAVED = auto()
    EXITED = auto()
    CGROUP_REMOVED = auto()


class EventCallback(Protocol):
    """이벤트와 이름 붙인 값을 전달받는 콜백의 형식"""

    def __call__(self, event: RunEvent, **details: object) -> None: ...
