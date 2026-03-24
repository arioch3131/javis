"""Shared operation view state for the integrated Operations panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


OperationKind = Literal["scan", "categorization", "organization", "generic"]
OperationStateName = Literal[
    "idle",
    "discovering",
    "running",
    "paused",
    "cancelling",
    "completed",
    "failed",
]
OperationAction = Literal["cancel", "pause", "resume", "close", "retry", "open_target"]


@dataclass(slots=True)
class OperationStat:
    label: str
    value: str
    hint: str = ""


@dataclass(slots=True)
class OperationDetail:
    label: str
    value: str


@dataclass(slots=True)
class OperationViewState:
    operation_id: str
    kind: OperationKind
    title: str
    state: OperationStateName
    summary: str
    current_item: str = ""
    progress_current: int = 0
    progress_total: int = 0
    is_determinate: bool = False
    stats: list[OperationStat] = field(default_factory=list)
    details: list[OperationDetail] = field(default_factory=list)
    log_entries: list[str] = field(default_factory=list)
    primary_action: OperationAction | None = None
    secondary_action: OperationAction | None = None
    primary_action_label: str | None = None
    secondary_action_label: str | None = None
