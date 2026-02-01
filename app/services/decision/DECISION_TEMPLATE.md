# Decision Template

기존 프로젝트의 AI 모델 기반 Decision 추출 시스템을 참고하여 만든 의사결정 템플릿입니다.

## 📋 Decision 모델 구조

### Core Fields (필수)
```python
class Decision(BaseModel):
    """Single decision extracted from messages with extended metadata"""
    # Core fields
    title: str              # 의사결정 제목 (max: 200자)
    owner: str             # 담당자/책임자
    deadline: str          # 완료 기한 (ISO format: YYYY-MM-DD)
    context: str           # 배경/맥락 정보
```

### Extended Fields (상태 추적)
```python
    # Status tracking
    status: DecisionStatus  # 상태: open, blocked, in_progress, completed, cancelled
    
    # Metadata
    priority: str          # 우선순위: low, medium, high, critical
    category: Optional[str] # 카테고리: schedule, technical, business, policy, resource
    
    # Timestamps
    created_at: datetime   # 의사결정 생성 시간 (자동 생성)
    updated_at: datetime   # 최종 수정 시간 (자동 갱신)
    
    # Additional notes
    notes: str            # 진행 상황 메모
```

### DecisionStatus Enum
```python
class DecisionStatus(str, Enum):
    OPEN = "open"                  # 아직 시작되지 않음
    BLOCKED = "blocked"            # 외부 요인에 의해 차단됨
    IN_PROGRESS = "in_progress"    # 현재 진행 중
    COMPLETED = "completed"        # 완료됨
    CANCELLED = "cancelled"        # 취소됨
```

## 🎯 Decision 템플릿 예시

### 1️⃣ 프로젝트 런칭 의사결정

```json
{
  "title": "런칭일을 다음 주 화요일로 고정",
  "owner": "프로젝트 리더",
  "deadline": "2026-02-04",
  "context": "개발팀 금요일 배포 완료, 결제 오류는 금요일 18시까지 해결 여부 재확인 후 최종 GO/NO GO 판단",
  "status": "open",
  "priority": "high",
  "category": "schedule",
  "created_at": "2026-01-30T10:00:00",
  "updated_at": "2026-01-30T10:00:00",
  "notes": ""
}
```

### 2️⃣ 기술 구현 의사결정

```json
{
  "title": "SDK 버전 업데이트 진행",
  "owner": "개발팀",
  "deadline": "2026-02-02T18:00:00Z",
  "context": "iOS 17 콜백 누락 문제 해결을 위해 SDK 버전 올림. QA 금요일 집중, 주말 핫픽스 준비",
  "status": "in_progress",
  "priority": "critical",
  "category": "technical",
  "created_at": "2026-01-28T14:30:00",
  "updated_at": "2026-01-30T09:15:00",
  "notes": "iOS SDK 4.7 버전 배포 준비 중. 핫픽스 패치 예정"
}
```

### 3️⃣ 마케팅 예산 의사결정

```json
{
  "title": "마케팅 예산 배분: 인스타 150만, 구글 150만, 리타겟팅 100만 (총 400만)",
  "owner": "마케팅 팀",
  "deadline": "2026-02-03",
  "context": "신규 유입과 재방문 밸런스 고려. 리타겟팅 강화로 재방문율 향상",
  "status": "completed",
  "priority": "medium",
  "category": "business",
  "created_at": "2026-01-25T11:00:00",
  "updated_at": "2026-01-30T15:45:00",
  "notes": "예산 승인 완료. 광고 집행 시작"
}
```

### 4️⃣ 정책 의사결정

```json
{
  "title": "환불 정책 확정: 결제 후 7일 이내 전액 환불",
  "owner": "결제팀 & 정책팀",
  "deadline": "2026-02-03T17:00:00Z",
  "context": "부분환불 로직 미구현으로 단순화. 추후 고도화 예정",
  "status": "open",
  "priority": "high",
  "category": "policy",
  "created_at": "2026-01-29T13:20:00",
  "updated_at": "2026-01-29T13:20:00",
  "notes": "법무팀 검토 대기 중"
}
```

---

## 📝 Decision 작성 가이드라인

### Title (제목) 작성 규칙
✅ **명확하고 구체적**
- "런칭일을 다음 주 화요일로 고정"
- "SDK 버전을 4.5에서 4.7로 업데이트"

❌ **모호하거나 추상적**
- "회의 진행"
- "변경 사항 검토"

### Owner (담당자) 지정 원칙
✅ **구체적인 담당자 또는 팀**
- "김철수 (개발리더)"
- "마케팅팀"
- "결제팀 & 법무팀"

❌ **너무 추상적**
- "Everyone"
- "Team"

### Deadline (기한) 설정
✅ **명확한 날짜/시간**
- `"2026-02-15"` (날짜만)
- `"2026-02-15T18:00:00Z"` (시간 포함)

❌ **모호한 표현**
- "ASAP"
- "가능한 한 빨리"

### Context (맥락) 기술
✅ **의사결정의 배경, 이유, 영향**
```
"개발팀 금요일 배포 완료 예정이고, 마케팅 광고는 월요일 시작 예정이므로 
화요일 런칭이 타이밍상 최적. 단, 결제 오류 해결이 선행되어야 함."
```

❌ **너무 짧거나 없음**
```
"런칭하기로 함"
```

---

## 🔄 Decision 추출 프롬프트

프로젝트에서 사용하는 AI 모델 기반 추출 프롬프트:

```
Extract key decisions from the conversation.
List each decision as (title, owner, deadline):

{conversation_text}
```

**Model**: LGAI-EXAONE/EXAONE-4.0-1.2B  
**Max Length**: 300 tokens  
**Min Length**: 50 tokens

---

## 💾 Decision 데이터 구조

### API Request
```json
POST /api/decisions
{
  "messages": [
    "오늘 런칭 준비 회의 대신 메신저로 진행할게요.",
    "현재 남은 이슈는 결제 오류, 온보딩 문구 확정, CS 매뉴얼 초안입니다.",
    "런칭일을 다음 주 화요일로 고정할까요? 아니면 안정화 위해 미룰까요.",
    "그럼 런칭일은 다음 주 화요일로 하고, 결제 오류는 금요일 밤까지 해결 여부 보고해서 GO/NO GO 체크하죠."
  ]
}
```

### API Response
```json
{
  "data": [
    {
      "title": "런칭일을 다음 주 화요일로 고정",
      "owner": "프로젝트 리더",
      "deadline": "2026-02-04",
      "context": "개발팀 금요일 배포 가능, 결제 오류는 금요일 18시까지 상황 공유 후 GO/NO GO 판단",
      "status": "open",
      "priority": "high",
      "category": "schedule",
      "created_at": "2026-01-30T10:00:00",
      "updated_at": "2026-01-30T10:00:00",
      "notes": ""
    },
    {
      "title": "결제 오류 해결 여부 금요일 18시 보고",
      "owner": "개발팀",
      "deadline": "2026-01-31T18:00:00Z",
      "context": "GO/NO GO 최종 판단을 위해 금요일 밤까지 결제 오류 해결 여부 확인",
      "status": "in_progress",
      "priority": "critical",
      "category": "technical",
      "created_at": "2026-01-30T10:05:00",
      "updated_at": "2026-01-30T14:30:00",
      "notes": "결제 시스템 검증 중. 토큰 갱신 로직 수정 완료"
    }
  ],
  "meta": {
    "count": 2,
    "timestamp": "2026-01-30T15:00:00Z",
    "processing_time_ms": 123
  }
}
```

---

## 🎨 Decision 카테고리 분류

의사결정을 다음과 같이 분류할 수 있습니다:

### 1. 일정/계획 (Schedule)
```json
{
  "title": "런칭일 결정",
  "category": "schedule",
  "owner": "프로젝트 리더",
  "deadline": "2026-02-04"
}
```

### 2. 기술 결정 (Technical)
```json
{
  "title": "기술 스택 선택",
  "category": "technical",
  "owner": "개발팀",
  "deadline": "2026-02-02"
}
```

### 3. 비즈니스 결정 (Business)
```json
{
  "title": "가격 책정 전략",
  "category": "business",
  "owner": "마케팅팀",
  "deadline": "2026-02-01"
}
```

### 4. 정책 결정 (Policy)
```json
{
  "title": "환불 정책 수립",
  "category": "policy",
  "owner": "정책팀",
  "deadline": "2026-02-03"
}
```

### 5. 리소스 할당 (Resource)
```json
{
  "title": "예산 배분",
  "category": "resource",
  "owner": "재무팀",
  "deadline": "2026-01-31"
}
```

---

## ✅ Decision 체크리스트

Decision을 추출하거나 생성할 때 다음을 확인하세요:

**Core Fields**
- [ ] **Title**: 명확하고 구체적인가? (200자 이내)
- [ ] **Owner**: 담당자가 명시되어 있는가?
- [ ] **Deadline**: 구체적인 날짜/시간인가? (ISO format)
- [ ] **Context**: 의사결정 배경이 충분히 설명되어 있는가?

**Extended Fields**
- [ ] **Status**: 적절한 상태로 설정되어 있는가? (open, in_progress, completed, blocked, cancelled)
- [ ] **Priority**: 우선순위가 명확히 지정되어 있는가? (low, medium, high, critical)
- [ ] **Category**: 적절한 카테고리로 분류되어 있는가? (schedule, technical, business, policy, resource)
- [ ] **Notes**: 진행 중 중요 메모가 기록되어 있는가?

**Quality Check**
- [ ] **Actionable**: 실행 가능한 결정인가?
- [ ] **Trackable**: 진행 상황을 추적할 수 있는가?

---

## 📊 Decision 상태 관리

Extended Decision 모델은 다음의 상태 값을 지원합니다:

```python
class DecisionStatus(str, Enum):
    OPEN = "open"                  # 아직 시작되지 않음
    BLOCKED = "blocked"            # 외부 요인에 의해 차단됨
    IN_PROGRESS = "in_progress"    # 현재 진행 중
    COMPLETED = "completed"        # 완료됨
    CANCELLED = "cancelled"        # 취소됨
```

### 상태 전환 흐름

1. **OPEN** → **IN_PROGRESS**: 실제 작업이 시작되면 업데이트
2. **IN_PROGRESS** → **BLOCKED**: 외부 요인으로 차단된 경우
3. **BLOCKED** → **IN_PROGRESS**: 문제 해결 후 다시 실행
4. **IN_PROGRESS** → **COMPLETED**: 작업 완료
5. **[ANY]** → **CANCELLED**: 의사결정 취소

**설명**: 현재 Decision 모델은 Extended 버전으로 확장되어 status, priority, category, timestamps, notes 필드를 기본 포함합니다.

---

## 🚀 프로젝트 내 활용

### 1. API 호출
```bash
curl -X POST "http://localhost:8000/api/decisions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": ["오늘 회의에서...", "이렇게 결정했습니다..."]
  }'
```

### 2. 응답 처리
```python
response = requests.post(
    "http://localhost:8000/api/decisions",
    json={"messages": messages}
)

data = response.json()
print(f"Total decisions: {data['meta']['count']}")

for decision in data["data"]:
    print(f"\n🎯 {decision.get('title')}")
    print(f"   담당자: {decision.get('owner')}")
    print(f"   기한: {decision.get('deadline')}")
    print(f"   상태: {(decision.get('status') or '').upper()}")
    print(f"   우선순위: {(decision.get('priority') or '').upper()}")
    print(f"   카테고리: {decision.get('category')}")
    print(f"   날짜: {decision.get('created_at')}")
    notes = decision.get('notes')
    if notes:
        print(f"   메모: {notes}")
```

---

## 📚 참고 자료

- **모델**: LGAI-EXAONE/EXAONE-4.0-1.2B
- **Framework**: FastAPI + Pydantic
- **AI Processor**: AIProcessor (app/services/ai_processor.py)
- **Response Model**: DecisionResponse (app/models.py)
