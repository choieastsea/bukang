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
네트워크 격리와 별도 터미널(PTY)은 아직 구성하지 않습니다.

`-d`를 지정하면 초기화와 상태 저장 후 UUID를 출력하고 CLI가 종료됩니다.

```bash
sudo .venv/bin/bukang run -d ~/tmproot /bin/sleep 300
```

컨테이너의 stdin은 `/dev/null`, stdout과 stderr는
`/var/lib/bukang/workspaces/<UUID>/container.log`에 연결합니다.
입력을 기다리는 셸은 EOF를 받고 바로 종료할 수 있으므로 계속 실행할 명령을 지정합니다.
백그라운드 컨테이너가 종료돼도 종료 코드는 기록하지 않으며, cgroup과 파일은 남습니다.

## 컨테이너 목록

```bash
sudo .venv/bin/bukang ps
```

저장된 컨테이너의 UUID, PID, 실행 여부, 명령을 표시합니다.
실행 여부는 저장된 PID·시작 시점·부팅 ID를 현재 호스트 정보와 비교해 판단합니다.
종료된 컨테이너도 표시하며, 이때 PID는 `-`로 표시합니다.

## 컨테이너 삭제

```bash
sudo .venv/bin/bukang rm <UUID>
```

`ps`에 표시된 전체 UUID를 지정합니다. 실행 중이면 삭제를 거부합니다.
종료된 컨테이너의 cgroup, 작업 디렉터리(변경 파일·로그), 상태 파일을 삭제하며
입력으로 사용한 원본 rootfs는 유지합니다.
