"""API 응답 유틸 함수."""
from flask import jsonify


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: dict | None = None,
):
    """
    공통 에러 응답 반환.
    Returns: (Response, status_code) tuple
    """
    return (
        jsonify({
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        }),
        status_code,
    )
