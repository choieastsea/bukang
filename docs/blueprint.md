# bukang CLI blueprint

![bukang](bukang.png)

## concept

부캉이는 나가고 싶지 않다.

따라서 호스트와 격리된 환경이 필요하다(?) 격리에 필요한 것들을 부캉이가 친절하게 알려준다.

## runtime dependencies

- python 3.13+
  - cli layer: [textual](https://github.com/textualize/textual)
  - ..?

## Architecture

- 컨테이너 생성/실행을 위한 런타임
- 감독 프로세스 (containerd-shim / conmon like) + TUI

## Phase

1. 실행 가능한 python cli 패키지 구성 (entry point)
2. 입출력 인터페이스 구현
3. python으로 기존 shell script 마이그레이션 (network 제외)
   - python에서 지원하는 API를 우선적으로 채택한다. 만약 추가 의존성 필요하다면 어쩔 수 없음
   - 아닌 경우 : `subprocess.run()`
4. 컨테이너 실행 (foreground)
5. 실행중인 컨테이너 영속화(json / sqlite) -> 실행중인 컨테이너 리스트
6. 컨테이너 백그라운드 실행
7. port binding option

## 주요 기능

- bukang run
- bukang ps
- bukang stop
- bukang rm

### possible...

- 호스트와 격리된 컨테이너 환경 구성 및 실행

### impossible...

- OCI image를 export하는 내장 기능 -> 어떻게 하는지는 알아보고 어려우면 docker export 사용
- 네트워크 스택의 일부
