# AsyncDispatcher 모듈 구조

Dispatcher를 읽기 쉽게 여러 파일로 분리했습니다.

## 파일 구조

```text
app/services/dispatcher/
├── __init__.py           # 패키지 진입점
├── async_dispatcher.py   # 메인 디스패처 (조정자)
├── task_queue.py         # 큐 관리
└── worker.py             # 워커 로직
```

## 각 모듈 설명

### 1. `async_dispatcher.py` - 메인 디스패처

**역할**: 전체 시스템 조정, 워커와 큐 관리

**주요 메서드**:

- `start()` - 워커 풀 시작
- `submit_task()` - 작업 제출
- `shutdown()` - 종료 처리
- `wait_completion()` - 모든 작업 완료 대기

**코드 길이**: ~190줄 (기존 256줄에서 단축)

### 2. `task_queue.py` - 태스크 큐

**역할**: 작업 큐 관리, 크기 제한

**주요 메서드**:

- `put()` - 작업 추가 (블로킹/논블로킹)
- `get()` - 작업 가져오기
- `join()` - 모든 작업 완료 대기

**속성**:

- `size` - 현재 큐 크기
- `is_full` - 큐가 가득 찼는지
- `is_empty` - 큐가 비었는지

**코드 길이**: ~100줄

### 3. `worker.py` - 워커

**역할**: 실제 작업 처리

**주요 메서드**:

- `run()` - 워커 메인 루프
- `_execute_task()` - 작업 실행 (타임아웃 포함)
- `_execute_callback()` - 콜백 실행 (에러 격리)

**코드 길이**: ~101줄

## 의존성 관계

```text
AsyncDispatcher
    ├── TaskQueue (1개)
    │   └── asyncio.Queue
    │
    └── Worker (여러 개)
        └── TaskQueue 참조
```

## 사용 방법

### 기본 사용 (변경 없음)

```python
from app.services.dispatcher import AsyncDispatcher

# 이전과 동일하게 사용
dispatcher = AsyncDispatcher(max_workers=5)
await dispatcher.start()
await dispatcher.submit_task(my_task())
await dispatcher.shutdown()
```

### 개별 컴포넌트 사용 (고급)

```python
from app.services.dispatcher import TaskQueue, Worker

# 커스텀 큐 생성
queue = TaskQueue(max_size=500)
await queue.put(my_task())

# 커스텀 워커 생성
worker = Worker(
    worker_id=1,
    task_queue=queue._queue,
    task_timeout=30.0
)
worker.start()
```

## 장점

### 1. 가독성 향상

- **이전**: 256줄의 단일 파일
- **이후**: 3개 파일로 분리 (각 100줄 내외)
- 각 파일이 명확한 책임을 가짐

### 2. 유지보수 용이

```text
워커 로직 수정 → worker.py만 수정
큐 로직 수정 → task_queue.py만 수정
전체 흐름 수정 → async_dispatcher.py만 수정
```

### 3. 테스트 용이

```python
# 개별 컴포넌트 단위 테스트 가능
def test_worker():
    worker = Worker(...)
    # 워커만 테스트


def test_queue():
    queue = TaskQueue(...)
    # 큐만 테스트


def test_dispatcher():
    dispatcher = AsyncDispatcher(...)
    # 통합 테스트
```

### 4. 확장 용이

- 새로운 워커 타입 추가 가능 (e.g. PriorityWorker)
- 새로운 큐 타입 추가 가능 (e.g. PriorityQueue)
- 각 컴포넌트를 독립적으로 확장

## 비교

### 이전 (단일 파일)

```python
# dispatcher.py (256줄)
class AsyncDispatcher:
    def __init__(self, ...):

    # 초기화 (47줄)

    async def _worker(self, ...):

    # 워커 로직 (67줄)

    async def start(self, ...):
# 시작 로직 (15줄)

# ... 나머지 메서드들 (127줄)
```

**문제점**:

- 한 파일이 너무 김
- 워커 로직과 큐 로직이 섞여 있음
- 수정 시 전체 파일을 읽어야 함

### 이후 (모듈화)

```python
# async_dispatcher.py (190줄) - 조정자
# task_queue.py (100줄) - 큐 관리
# worker.py (101줄) - 작업 처리
```

**장점**:

- 각 파일이 100줄 내외로 짧음
- 책임이 명확히 분리됨
- 필요한 파일만 열어서 수정

## 마이그레이션

### 기존 코드

```python
from app.services.dispatcher import AsyncDispatcher
```

**→ 변경 필요 없음!** 동일하게 작동합니다.

### 내부 구현 변경

**이전**:

```python
dispatcher.task_queue.qsize()  # asyncio.Queue 직접 접근
```

**이후**:

```python
dispatcher.queue.size  # TaskQueue 래퍼 사용
```

## 파일 크기 비교

| 파일                  |    이전    |    이후    |
|:--------------------|:--------:|:--------:|
| dispatcher.py       |   256줄   |    -     |
| async_dispatcher.py |    -     |   190줄   |
| task_queue.py       |    -     |   100줄   |
| worker.py           |    -     |   101줄   |
| **총합**              | **256줄** | **391줄** |

> 줄 수는 늘었지만, 각 파일이 짧아져서 훨씬 읽기 쉽습니다!

## 다음 개선 방향

1. **PriorityQueue 추가**: 우선순위 큐 지원
2. **WorkerPool 추가**: 워커 관리 전담 클래스
3. **Metrics 추가**: 성능 모니터링
4. **Retry 로직**: 실패한 작업 재시도

