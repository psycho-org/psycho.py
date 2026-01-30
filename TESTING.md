# Testing Guide - Psycho AI Server

이 문서는 Psycho AI Server의 테스트 실행 방법과 테스트 구조를 설명합니다.

## 📋 테스트 구조

```
tests/
├── __init__.py           # Tests 패키지
├── conftest.py          # Pytest fixtures와 설정
└── test_api_endpoints.py # API 엔드포인트 테스트
```

## 🚀 테스트 실행

### 1. 필수 패키지 설치

```bash
# 프로젝트 루트에서 가상 환경 활성화
source .venv/bin/activate  # macOS/Linux
# 또는
.venv\Scripts\activate  # Windows

# 필수 패키지 설치
pip install pytest pytest-asyncio fastapi httpx
```

### 2. 모든 테스트 실행

```bash
# 기본 실행
pytest tests/

# 상세 출력
pytest tests/ -v

# 커버리지 함께 실행
pytest tests/ --cov=app --cov-report=html
```

### 3. 특정 테스트 클래스 또는 함수 실행

```bash
# 특정 클래스의 모든 테스트
pytest tests/test_api_endpoints.py::TestHealthEndpoints -v

# 특정 테스트 함수
pytest tests/test_api_endpoints.py::TestDecisionsEndpoint::test_extract_decisions_success -v

# 특정 키워드로 필터링
pytest tests/ -k "decisions" -v
```

### 4. 실시간 모니터링

```bash
# pytest-watch 설치 (선택사항)
pip install pytest-watch

# 파일 변경 시 자동 실행
ptw tests/
```

## 📊 테스트 항목

### Health & Info Tests
- `test_health_check`: GET /health 엔드포인트 테스트
- `test_root_endpoint`: GET / 엔드포인트 테스트

### Summarize Endpoint Tests
- `test_summarize_success`: 정상 요약 처리
- `test_summarize_empty_messages`: 빈 메시지 리스트 에러 처리
- `test_summarize_service_unavailable`: 서비스 불가 에러 처리

### Decisions Endpoint Tests
- `test_extract_decisions_success`: 정상 Decision 추출
- `test_extract_decisions_empty_messages`: 빈 메시지 리스트 에러 처리
- `test_extract_decisions_response_structure`: 응답 구조 검증
  - data 배열 구조 확인
  - meta 메타데이터 확인
  - 필드 값 검증 (status, priority, category)

### Catchup Endpoint Tests
- `test_generate_catchup_success`: 정상 Catchup 생성
- `test_generate_catchup_empty_messages`: 빈 메시지 리스트 에러 처리
- `test_generate_catchup_service_unavailable`: 서비스 불가 에러 처리

### Error Handling Tests
- `test_timeout_error_handling`: TimeoutError 처리 (504)
- `test_queue_full_error_handling`: QueueFull 처리 (429)
- `test_runtime_error_handling`: RuntimeError 처리 (503)

### Input Validation Tests
- `test_summarize_invalid_message_type`: 잘못된 메시지 타입 검증
- `test_decisions_max_messages`: 최대 메시지 수 제한 (100)
- `test_decisions_exceed_max_messages`: 최대 메시지 수 초과 (101)

## 🔧 Fixtures

`conftest.py`에서 제공하는 테스트 픽스처:

### `client`
- FastAPI TestClient 인스턴스
- Mock AsyncDispatcher와 함께 초기화됨
- 모든 API 엔드포인트 테스트에 사용

```python
def test_example(client):
    response = client.get("/health")
    assert response.status_code == 200
```

### `mock_dispatcher`
- Mock AsyncDispatcher 객체
- `is_running=True`, `submit_task=AsyncMock()` 설정
- 에러 시뮬레이션에 사용 가능

```python
def test_with_dispatcher(client, mock_dispatcher):
    mock_dispatcher.is_running = False
    # 테스트 진행
```

### `sample_messages`
- 테스트용 샘플 메시지 4개
- 실제 대화 시뮬레이션

```python
def test_with_samples(client, sample_messages):
    response = client.post("/api/decisions", json={"messages": sample_messages})
```

### `event_loop`
- Pytest의 이벤트 루프 (async 테스트용)
- Session 스코프로 재사용

## 💡 테스트 작성 가이드

### Mock 사용 예시

```python
from unittest.mock import patch

@patch('app.services.ai_processor.AIProcessor.extract_decisions')
def test_my_test(self, mock_extract, client, sample_messages):
    # Mock 설정
    from app.models import Decision, DecisionStatus
    from datetime import datetime, UTC
    
    mock_extract.return_value = [
        Decision(
            title="테스트",
            owner="테스트",
            deadline="2026-02-04",
            context="테스트",
            status=DecisionStatus.OPEN,
            priority="high",
            category="schedule",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notes=""
        )
    ]
    
    # 테스트 실행
    response = client.post("/api/decisions", json={"messages": sample_messages})
    
    # 검증
    assert response.status_code == 202
    data = response.json()
    assert data["meta"]["count"] == 1
```

### Async 테스트 예시

```python
@pytest.mark.asyncio
async def test_async_operation(mock_dispatcher):
    from app.services.ai_processor import AIProcessor
    
    processor = AIProcessor(dispatcher=mock_dispatcher)
    # 비동기 작업 테스트
```

## 📈 커버리지 보고서

```bash
# HTML 커버리지 보고서 생성
pytest tests/ --cov=app --cov-report=html

# 생성된 htmlcov/index.html 을 브라우저에서 열기
open htmlcov/index.html
```

## 🐛 디버깅

### Verbose 출력

```bash
pytest tests/ -vv  # 매우 상세한 출력
```

### Breakpoint 사용

```python
def test_debug():
    breakpoint()  # 여기서 실행 중지
    # 테스트 계속
```

### 실패한 테스트만 재실행

```bash
pytest tests/ --lf  # last failed
pytest tests/ --ff  # failed first
```

### 스택 트레이스 상세 출력

```bash
pytest tests/ --tb=long
```

## 🔄 CI/CD 통합

GitHub Actions 예시:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app
```

## 📝 일반적인 에러 및 해결책

### ImportError: No module named 'fastapi'
```bash
# 해결: 필수 패키지 설치
pip install fastapi httpx pytest pytest-asyncio
```

### ModuleNotFoundError: No module named 'app'
```bash
# 해결: 프로젝트 루트 디렉토리에서 실행
cd /path/to/psycho.py
pytest tests/
```

### asyncio.TimeoutError
```bash
# 해결: pytest-asyncio 설치
pip install pytest-asyncio
```

### Fixture 'client' not found
```bash
# 해결: conftest.py가 tests/ 디렉토리에 있는지 확인
ls tests/conftest.py
```

## 📚 추가 리소스

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
- [Unittest Mock](https://docs.python.org/3/library/unittest.mock.html)
- [Python asyncio Testing](https://docs.python.org/3/library/asyncio-dev.html#debug-mode)
