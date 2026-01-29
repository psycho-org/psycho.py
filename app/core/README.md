# Core Package

앱의 핵심 기능을 담당하는 패키지입니다.

## 구조

```
app/core/
├── __init__.py
└── lifespan.py      # FastAPI 앱 생명주기 관리
```

## 포함된 모듈

### `lifespan.py`
FastAPI 앱의 시작(startup)과 종료(shutdown) 로직을 관리합니다.

**기능:**
- Dispatcher 초기화 및 시작
- 앱 종료 시 Dispatcher graceful shutdown

**사용:**
```python
from app.core import lifespan

app = FastAPI(lifespan=lifespan)
```

## 향후 확장

이 패키지에 추가될 수 있는 모듈:

### `dependencies.py` (예정)
FastAPI dependency injection 함수들
```python
# app/core/dependencies.py
from fastapi import Depends, Request

async def get_dispatcher(request: Request):
    return request.app.state.dispatcher
```

### `security.py` (예정)
인증/인가 관련 로직
```python
# app/core/security.py
async def verify_api_key(api_key: str):
    ...
```

### `events.py` (예정)
앱 이벤트 핸들러
```python
# app/core/events.py
async def on_startup():
    ...

async def on_shutdown():
    ...
```

## 왜 core 패키지?

### 장점
1. **명확한 구조**: 앱의 "핵심" 로직임이 명확
2. **확장성**: 관련 모듈 추가 용이
3. **업계 표준**: FastAPI 프로젝트에서 널리 사용
4. **관심사 분리**: 비즈니스 로직(services)과 분리

### 비교

**이전:**
```
app/
├── lifespan.py      # 루트에 단독
├── routes/
└── services/
```

**현재:**
```
app/
├── core/            # 핵심 기능 그룹화
│   └── lifespan.py
├── routes/
└── services/
```

## Import 방법

### 방법 1: 패키지에서 직접 import (권장)
```python
from app.core import lifespan
```

### 방법 2: 모듈에서 import
```python
from app.core.lifespan import lifespan
```

둘 다 동작하지만, 방법 1이 더 간결합니다.
