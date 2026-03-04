"""DB 관련 유틸 함수."""
from bson import ObjectId
from bson.errors import InvalidId


def parse_object_id(value: str):
    """
    문자열을 ObjectId로 변환.
    유효하지 않으면 None 반환.
    """
    if not value:
        return None
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None
