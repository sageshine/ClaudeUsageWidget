from dataclasses import dataclass
from datetime import datetime


@dataclass
class LimitInfo:
    percent: int
    resets_at: datetime


@dataclass
class ScopedLimit:
    model_name: str
    percent: int
    resets_at: datetime


@dataclass
class CreditInfo:
    enabled: bool
    percent: int
    used_dollars: float
    limit_dollars: float | None


@dataclass
class UsageSnapshot:
    session: LimitInfo
    weekly_all: LimitInfo
    weekly_scoped: list
    credit: CreditInfo
    fetched_at: datetime
