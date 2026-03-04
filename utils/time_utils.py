"""시간 관련 유틸 함수."""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """현재 UTC 시각 반환 (timezone-aware)."""
    return datetime.now(timezone.utc)
