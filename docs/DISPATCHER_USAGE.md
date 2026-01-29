# Dispatcher 사용 가이드

## 핵심 개념

**Dispatcher는 하나, 모든 API 파일에서 공유합니다.**

```
FastAPI 앱 시작
    ↓
main.py에서 Dispatcher 생성 (1개)
    ↓
app.state.dispatcher에 저장 ← 여기가 핵심!
    ↓
모든 API 파일에서 request.app.state.dispatcher로 접근
```

## 설정 방법

### 1. main.py에서 Dispatcher 초기화

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.dispatcher import AsyncDispatcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시
    dispatcher = AsyncDispatcher(
        max_workers=5,
        max_queue_size=100,
        task_timeout=60.0
    )
    await dispatcher.start()
    app.state.dispatcher = dispatcher  # ✅ app.state에 저장
    
    yield
    
    # 앱 종료 시
    await app.state.dispatcher.shutdown()

app = FastAPI(lifespan=lifespan)  # ✅ lifespan 연결
```

**핵심**: `app.state.dispatcher = dispatcher`로 저장하면 끝!

### 2. 각 API 파일에서 사용

```python
# app/routes/your_api.py
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/your-endpoint")
async def your_endpoint(request: Request, data: dict):
    # ✅ request.app.state로 접근
    dispatcher = request.app.state.dispatcher
    
    # 작업 제출
    await dispatcher.submit_task(your_task())
    
    return {"status": "queued"}
```

**핵심**: `request.app.state.dispatcher`로 접근!

## 왜 app.state를 사용하나요?

### ❌ Global 변수의 문제점

```python
# 나쁜 예시
dispatcher = None  # Global

@asynccontextmanager
async def lifespan(app: FastAPI):
    global dispatcher  # 🚫 global 사용
    dispatcher = AsyncDispatcher()
```

**문제**:
- 테스트하기 어려움
- 멀티프로세스에서 문제
- 코드가 지저분함

### ✅ app.state의 장점

```python
# 좋은 예시
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.dispatcher = AsyncDispatcher()  # ✅ app.state 사용
```

**장점**:
- Global 불필요
- 테스트 용이
- FastAPI 권장 방식
- 타입 안전

## 사용 패턴

### 패턴 1: 기본 사용

```python
@router.post("/process")
async def process(request: Request, data: dict):
    dispatcher = request.app.state.dispatcher
    
    async def task():
        # 시간이 오래 걸리는 작업
        result = await heavy_processing(data)
        return result
    
    await dispatcher.submit_task(task())
    
    return {"status": "queued"}
```

### 패턴 2: 안전한 사용 (체크 포함)

```python
@router.post("/process")
async def process(request: Request, data: dict):
    dispatcher = request.app.state.dispatcher
    
    # 1. Dispatcher 사용 가능 체크
    if dispatcher is None or not dispatcher.is_running:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    # 2. 큐 가득 참 체크
    if dispatcher.is_queue_full:
        raise HTTPException(status_code=429, detail="Queue full")
    
    # 3. 작업 제출
    await dispatcher.submit_task(task(), block=False)
    
    return {"status": "queued"}
```

### 패턴 3: 콜백 사용

```python
@router.post("/process")
async def process(request: Request, data: dict):
    dispatcher = request.app.state.dispatcher
    
    def on_complete(result):
        # DB에 결과 저장
        save_to_db(result)
        # 웹훅 호출
        send_webhook(result)
    
    await dispatcher.submit_task(task(), callback=on_complete)
    
    return {"status": "queued"}
```

## 여러 API 파일에서 사용하기

### 파일 구조

```
app/
├── main.py                 # Dispatcher 생성
└── routes/
    ├── summarize.py        # API 1
    ├── decisions.py        # API 2
    └── catchup.py          # API 3
```

### summarize.py

```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/summarize")
async def summarize(request: Request, messages: list):
    dispatcher = request.app.state.dispatcher
    
    async def summarize_task():
        return await ai_summarize(messages)
    
    await dispatcher.submit_task(summarize_task())
    return {"status": "processing"}
```

### decisions.py

```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/decisions")
async def decisions(request: Request, messages: list):
    dispatcher = request.app.state.dispatcher  # ✅ 같은 dispatcher!
    
    async def extract_decisions():
        return await ai_extract_decisions(messages)
    
    await dispatcher.submit_task(extract_decisions())
    return {"status": "processing"}
```

### catchup.py

```python
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/catchup")
async def catchup(request: Request, messages: list):
    dispatcher = request.app.state.dispatcher  # ✅ 같은 dispatcher!
    
    async def generate_catchup():
        return await ai_generate_catchup(messages)
    
    await dispatcher.submit_task(generate_catchup())
    return {"status": "processing"}
```

**모두 같은 dispatcher를 사용합니다!**

## 헬퍼 함수 만들기 (선택사항)

반복 코드를 줄이고 싶다면:

```python
# app/utils/dispatcher_helper.py
from fastapi import HTTPException, Request

def get_dispatcher(request: Request):
    """Dispatcher를 안전하게 가져오는 헬퍼 함수"""
    dispatcher = request.app.state.dispatcher
    
    if dispatcher is None or not dispatcher.is_running:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    return dispatcher

# 사용
from app.utils.dispatcher_helper import get_dispatcher

@router.post("/process")
async def process(request: Request, data: dict):
    dispatcher = get_dispatcher(request)  # ✅ 간단!
    await dispatcher.submit_task(task())
    return {"status": "queued"}
```

## Dependency Injection 사용 (고급)

FastAPI의 Depends를 사용하면 더 깔끔:

```python
# app/dependencies.py
from fastapi import Depends, HTTPException, Request

async def get_dispatcher(request: Request):
    """Dispatcher dependency"""
    dispatcher = request.app.state.dispatcher
    
    if dispatcher is None or not dispatcher.is_running:
        raise HTTPException(status_code=503, detail="Service unavailable")
    
    return dispatcher

# 사용
from app.dependencies import get_dispatcher

@router.post("/process")
async def process(
    data: dict,
    dispatcher = Depends(get_dispatcher)  # ✅ 자동 주입!
):
    await dispatcher.submit_task(task())
    return {"status": "queued"}
```

## 테스트하기

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.services.dispatcher import AsyncDispatcher

def test_process_endpoint():
    # Mock dispatcher
    mock_dispatcher = AsyncDispatcher(max_workers=1)
    await mock_dispatcher.start()
    
    # app.state에 설정
    app.state.dispatcher = mock_dispatcher
    
    client = TestClient(app)
    response = client.post("/api/process", json={"data": "test"})
    
    assert response.status_code == 200
```

## 요약

1. **main.py**에서 `app.state.dispatcher`에 저장
2. **각 API 파일**에서 `request.app.state.dispatcher`로 접근
3. Global 변수 불필요!
4. 모든 API가 같은 dispatcher 공유

```python
# main.py
app.state.dispatcher = AsyncDispatcher()  # 한 번만 생성

# 모든 API 파일
dispatcher = request.app.state.dispatcher  # 같은 것을 가져옴
```

간단하죠? 😊
