"""
Extended Decision models with dependency and impact tracking.

This module provides extended Decision models that add relationship and impact
tracking capabilities to the base Decision model defined in app.models.

Reference: app/models.py Decision class
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import Decision, DecisionStatus  # noqa: F401


# Alias for backward compatibility
DecisionWithStatus = Decision


class DecisionWithDependencies(Decision):
    """Decision with dependency tracking"""

    dependencies: list[str] = Field(
        default_factory=list,
        description="List of other decision titles this decision depends on"
    )
    blocks: list[str] = Field(
        default_factory=list,
        description="List of other decision titles blocked by this decision"
    )
    related_decisions: list[str] = Field(
        default_factory=list,
        description="List of related decision titles"
    )


class DecisionWithImpact(Decision):
    """Decision with impact assessment"""

    impact_area: str = Field(
        default="",
        description="Primary area affected by this decision (e.g., 'Engineering', 'Marketing')"
    )
    estimated_effort: str = Field(
        default="medium",
        description="Estimated effort to implement: low, medium, high, critical"
    )
    risk_level: str = Field(
        default="low",
        description="Risk assessment: low, medium, high, critical"
    )
    success_metrics: list[str] = Field(
        default_factory=list,
        description="Measurable success criteria"
    )


class DecisionBatch(BaseModel):
    """Batch of decisions extracted from a conversation"""

    decisions: list[Decision] = Field(
        default_factory=list,
        description="List of extracted decisions"
    )
    total_count: int = Field(
        ...,
        description="Total number of decisions"
    )
    extracted_from_messages: int = Field(
        ...,
        description="Number of messages analyzed"
    )
    extraction_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When decisions were extracted"
    )


# ==================== Utility Functions ====================

def create_decision(
    title: str,
    owner: str,
    deadline: str = "",
    context: str = "",
    priority: str = "medium",
    category: Optional[str] = None
) -> Decision:
    """
    Create a new Decision with status.
    
    Args:
        title: Decision title
        owner: Responsible person/team
        deadline: Optional deadline
        context: Decision background/rationale
        priority: Priority level
        category: Decision category
        
    Returns:
        Decision instance
    """
    return Decision(
        title=title,
        owner=owner,
        deadline=deadline,
        context=context,
        priority=priority,
        category=category
    )


def update_decision_status(
    decision: Decision,
    new_status: DecisionStatus,
    notes: str = ""
) -> Decision:
    """
    Update decision status and timestamp.
    
    Args:
        decision: Existing decision
        new_status: New status
        notes: Optional update notes
        
    Returns:
        Updated Decision instance
    """
    decision.status = new_status
    decision.updated_at = datetime.utcnow()
    if notes:
        decision.notes = notes
    return decision


def filter_decisions_by_status(
    decisions: list[Decision],
    status: DecisionStatus
) -> list[Decision]:
    """
    Filter decisions by status.
    
    Args:
        decisions: List of decisions
        status: Status to filter by
        
    Returns:
        Filtered list
    """
    return [d for d in decisions if d.status == status]


def filter_decisions_by_owner(
    decisions: list[Decision],
    owner: str
) -> list[Decision]:
    """
    Filter decisions by owner.
    
    Args:
        decisions: List of decisions
        owner: Owner name or team
        
    Returns:
        Filtered list
    """
    return [d for d in decisions if d.owner.lower() == owner.lower()]


def filter_decisions_by_priority(
    decisions: list[Decision],
    priority: str
) -> list[Decision]:
    """
    Filter decisions by priority.
    
    Args:
        decisions: List of decisions
        priority: Priority level
        
    Returns:
        Filtered list
    """
    return [d for d in decisions if d.priority.lower() == priority.lower()]


def get_overdue_decisions(
    decisions: list[Decision]
) -> list[Decision]:
    """
    Get decisions past their deadline.
    
    Args:
        decisions: List of decisions
        
    Returns:
        List of overdue decisions
    """
    now = datetime.utcnow()
    overdue = []

    for decision in decisions:
        if decision.deadline:
            try:
                deadline = datetime.fromisoformat(decision.deadline.replace('Z', '+00:00'))
                if deadline < now and decision.status != DecisionStatus.COMPLETED:
                    overdue.append(decision)
            except ValueError:
                # Invalid date format, skip
                pass

    return overdue


# ==================== Example Usage ====================

if __name__ == "__main__":
    # Create a decision
    decision1 = create_decision(
        title="런칭일을 다음 주 화요일로 고정",
        owner="프로젝트 리더",
        deadline="2026-02-04",
        context="개발팀 금요일 배포 완료, 결제 오류는 금요일 18시까지 해결 여부 재확인",
        priority="high",
        category="schedule"
    )

    print("Created Decision:")
    print(f"  Title: {decision1.title}")
    print(f"  Owner: {decision1.owner}")
    print(f"  Status: {decision1.status}")
    print(f"  Priority: {decision1.priority}")
    print()

    # Update decision status
    decision1 = update_decision_status(
        decision1,
        DecisionStatus.IN_PROGRESS,
        notes="시작됨 - 런칭 준비 진행 중"
    )

    print("Updated Decision:")
    print(f"  Status: {decision1.status}")
    print(f"  Notes: {decision1.notes}")
    print(f"  Updated: {decision1.updated_at}")
    print()

    # Create a batch of decisions
    decisions = [
        decision1,
        create_decision(
            title="SDK 버전 업데이트",
            owner="개발팀",
            deadline="2026-02-02T18:00:00Z",
            context="iOS 17 콜백 누락 문제 해결",
            priority="critical",
            category="technical"
        ),
        create_decision(
            title="마케팅 예산 배분",
            owner="마케팅팀",
            deadline="2026-02-03",
            context="신규 유입과 재방문 밸런스 고려",
            priority="high",
            category="resource"
        )
    ]

    batch = DecisionBatch(
        decisions=decisions,
        total_count=len(decisions),
        extracted_from_messages=10
    )

    print("Decision Batch:")
    print(f"  Total Decisions: {batch.total_count}")
    print(f"  From Messages: {batch.extracted_from_messages}")
    print()

    # Filter decisions
    high_priority = filter_decisions_by_priority(decisions, "high")
    print(f"High Priority Decisions: {len(high_priority)}")
    for d in high_priority:
        print(f"  - {d.title}")
    print()

    dev_team_decisions = filter_decisions_by_owner(decisions, "개발팀")
    print(f"Development Team Decisions: {len(dev_team_decisions)}")
    for d in dev_team_decisions:
        print(f"  - {d.title}")
