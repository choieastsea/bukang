# bukang

부캉이가 만들어주는 컨테이너 런타임

## 실행 방법

```bash
uv sync
source .venv/bin/activate
bukang
bukang --help
```

가상환경을 활성화하지 않을 때는 `uv run bukang`으로 실행합니다.

`bukang`과 `bukang --help`는 부캉이 픽셀 그림과 도움말을 표시합니다.

## 컨테이너 실행

학습용 Linux VM에서 root 권한으로 실행합니다. 압축 해제된 rootfs와
하위 그룹에 memory controller를 제공하는 cgroup v2 부모 경로가 필요합니다.

```bash
bukang run --help
bukang run --cgroup-parent /sys/fs/cgroup/bukang ./rootfs /bin/sh
bukang run ./rootfs /bin/sh -c 'echo hello'
```

부캉이 옵션은 rootfs 앞에 쓰고, 실행할 명령과 인자는 뒤에 씁니다.
메모리는 50 MiB로 제한하고 swap은 비활성화합니다. 종료 코드는 CLI에 전달하며,
상태와 쓰기 영역은 `/var/lib/bukang` 아래에 보존합니다.
현재 foreground 실행만 지원하며, 네트워크 격리와 별도 터미널(PTY)은 아직 구성하지 않습니다.
