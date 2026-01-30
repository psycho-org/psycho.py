"""Decision factory and helper functions"""

import json
import logging
import re
from datetime import datetime, UTC
from typing import Optional

from app.models import Decision, DecisionStatus

logger = logging.getLogger(__name__)


def dedup_decisions(decisions: list[Decision]) -> list[Decision]:
    """Remove duplicates by normalized (title, owner)."""
    seen: set[tuple[str, str]] = set()
    unique: list[Decision] = []
    for d in decisions:
        key = (d.title.strip().lower(), (d.owner or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique


def create_decision_from_dict(data: dict, context: str = "", messages_content: str = "") -> Optional[Decision]:
    """
    Create a Decision from a dictionary of extracted data.
    
    Args:
        data: Dictionary with decision fields from AI extraction
        context: Additional context (used as default)
        messages_content: Original messages content (used as fallback)
        
    Returns:
        Decision instance or None if creation fails
    """
    try:
        # Extract fields with defaults
        title = data.get('title', 'Unnamed Decision')[:200]
        owner = data.get('owner', 'Unknown')
        deadline = data.get('deadline', '')
        context_value = data.get('context', context or messages_content[:300])
        category = data.get('category', 'business')
        priority = data.get('priority', 'medium')
        notes = data.get('notes', 'Extracted from conversation')

        # Validate category
        valid_categories = ['schedule', 'technical', 'business', 'policy', 'resource']
        if category not in valid_categories:
            category = 'business'

        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'critical']
        if priority not in valid_priorities:
            priority = 'medium'

        return Decision(
            title=title,
            owner=owner,
            deadline=deadline,
            context=context_value,
            status=DecisionStatus.OPEN,
            priority=priority,
            category=category,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notes=notes
        )
    except Exception as e:
        logger.warning(f"Failed to create decision from dict: {e}")
        return None


def create_decision_from_text(text: str, messages_content: str = "") -> Optional[Decision]:
    """
    Create a Decision from extracted text line.
    
    Args:
        text: Single extracted decision text
        messages_content: Original messages content for context
        
    Returns:
        Decision instance or None if creation fails
    """
    try:
        if not text or len(text) < 5:
            return None

        return Decision(
            title=text.strip()[:200],
            owner="Unknown",
            deadline="",
            context=messages_content[:300] if messages_content else text,
            status=DecisionStatus.OPEN,
            priority="medium",
            category="business",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notes="Extracted from conversation"
        )
    except Exception as e:
        logger.warning(f"Failed to create decision from text: {e}")
        return None


def parse_decisions_from_json(extraction: str, messages_content: str = "") -> list[Decision]:
    """
    Parse decisions from JSON extraction response.
    Supports multiple independent JSON arrays embedded in free text.
    
    Args:
        extraction: JSON string from AI model
        messages_content: Original messages content for fallback context
        
    Returns:
        List of Decision objects
    """
    decisions: list[Decision] = []

    # Find all bracketed JSON array substrings non-greedily
    matches = list(re.finditer(r"\[.*?\]", extraction, flags=re.S))
    if not matches:
        return decisions

    for m in matches:
        array_text = m.group(0)
        try:
            parsed = json.loads(array_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON array from extraction segment: {e}")
            continue

        if not isinstance(parsed, list):
            continue

        for item in parsed:
            if isinstance(item, dict):
                decision = create_decision_from_dict(
                    item,
                    messages_content=messages_content
                )
                if decision:
                    decisions.append(decision)

    return decisions


def parse_decisions_from_lines(extraction: str, messages_content: str = "") -> list[Decision]:
    """
    Parse decisions from line-separated extraction (fallback).
    
    Args:
        extraction: Text with decisions separated by lines
        messages_content: Original messages content for context
        
    Returns:
        List of Decision objects
    """
    decisions: list[Decision] = []

    # Heuristics to ignore JSON/code-fence artifacts
    MAX_FALLBACK_ITEMS = 8
    for line in extraction.split('\n'):
        l = line.strip()
        if not l or len(l) < 10:
            continue
        if l.startswith("```"):
            continue
        if l[0] in ('"', "'"):
            continue
        if '":' in l or "':" in l:
            continue
        if l.endswith(',') or l.endswith('",'):
            continue

        decision = create_decision_from_text(l, messages_content)
        if decision:
            decisions.append(decision)
            if len(decisions) >= MAX_FALLBACK_ITEMS:
                break

    return dedup_decisions(decisions)


def create_placeholder_decision(messages_count: int, messages_content: str = "") -> Decision:
    """
    Create a placeholder decision when extraction yields no results.
    
    Args:
        messages_count: Number of messages analyzed
        messages_content: Original messages content for context
        
    Returns:
        Placeholder Decision instance
    """
    return Decision(
        title="Discussion Captured",
        owner="Team",
        deadline="",
        context=f"Analysis of {messages_count} messages" if messages_count > 0 else messages_content,
        status=DecisionStatus.OPEN,
        priority="medium",
        category="business",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        notes="Placeholder decision from conversation analysis"
    )
