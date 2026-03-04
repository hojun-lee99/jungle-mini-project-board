"""
보드 관련 API 라우트
- 보드 생성 (POST /api/boards)
- 내 보드 목록 (GET /api/boards)
- 보드 조회 (GET /api/boards/<public_id>)
- 보드 public_id 변경 (PATCH /api/boards/<public_id>)
- 보드 삭제 (DELETE /api/boards/<public_id>)
"""
import uuid

from flask import Blueprint, current_app, jsonify, request

boards_bp = Blueprint("boards", __name__, url_prefix="/api/boards")


def _get_current_user_id():
    """
    현재 로그인 사용자 ID 반환.
    TODO: JWT/세션 연동 후 실제 인증으로 교체.
    개발용: X-User-Id 헤더 사용.
    """
    return request.headers.get("X-User-Id")


def _serialize_board(doc, include_created_at=False):
    """boards 컬렉션 문서를 API 응답 형식으로 변환."""
    if not doc:
        return None
    out = {
        "id": str(doc["_id"]),
        "public_id": str(doc["public_id"]),
        "owner_user_id": str(doc["owner_user_id"]),
        "title": doc.get("title") or "",
    }
    if include_created_at and doc.get("created_at"):
        out["created_at"] = doc["created_at"].isoformat()
    return out


def _serialize_note(doc, image_base_url=None):
    """sticky_notes 컬렉션 문서를 API 응답 형식으로 변환."""
    if not doc:
        return None
    image_key = doc.get("image_key")
    image_url = None
    if image_key and image_base_url:
        image_url = f"{image_base_url.rstrip('/')}/{image_key}"
    return {
        "id": str(doc["_id"]),
        "owner_user_id": str(doc["owner_user_id"]),
        "text": doc.get("text") or "",
        "image_url": image_url,
        "x": doc.get("x", 0),
        "y": doc.get("y", 0),
        "z_index": doc.get("z_index", 0),
        "version": doc.get("version", 0),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }


# ---------------------------------------------------------------------------
# POST /api/boards - 보드 생성
# ---------------------------------------------------------------------------
@boards_bp.route("", methods=["POST"])
def create_board():
    """
    보드 생성 API
    - 인증: 필수
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}
        }), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    data = request.get_json(silent=True) or {}
    title = data.get("title") or ""

    now = __import__("datetime").datetime.utcnow()
    public_id = str(uuid.uuid4())

    doc = {
        "owner_user_id": user_id,
        "public_id": public_id,
        "title": title,
        "next_z_index": 0,
        "note_count": 0,
        "created_at": now,
        "updated_at": now,
    }

    boards = db["boards"]
    result = boards.insert_one(doc)
    doc["_id"] = result.inserted_id

    return jsonify(_serialize_board(doc, include_created_at=True)), 201


# ---------------------------------------------------------------------------
# GET /api/boards - 내 보드 목록
# ---------------------------------------------------------------------------
@boards_bp.route("", methods=["GET"])
def list_boards():
    """
    내 보드 목록 조회 API
    - 인증: 필수
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}
        }), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    skip = (page - 1) * limit

    boards = db["boards"]
    total = boards.count_documents({"owner_user_id": user_id})
    cursor = boards.find({"owner_user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    items = list(cursor)

    return jsonify({
        "boards": [_serialize_board(b, include_created_at=True) for b in items],
        "total": total,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/boards/<public_id> - 보드 조회
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>", methods=["GET"])
def get_board(public_id: str):
    """
    보드 조회 API
    - 인증: 불필요
    """
    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    boards = db["boards"]
    sticky_notes = db["sticky_notes"]

    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    board_id = board["_id"]
    notes_cursor = sticky_notes.find({"board_id": board_id}).sort("z_index", 1)
    notes_list = list(notes_cursor)

    image_base_url = current_app.config.get("IMAGE_BASE_URL") or ""

    return jsonify({
        "board": _serialize_board(board),
        "notes": [_serialize_note(n, image_base_url) for n in notes_list],
    }), 200


# ---------------------------------------------------------------------------
# PATCH /api/boards/<public_id> - public_id 변경
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>", methods=["PATCH"])
def update_board(public_id: str):
    """
    보드 public_id 변경 API
    - 인증: 필수 (보드 생성자만)
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}
        }), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    data = request.get_json(silent=True) or {}
    new_public_id = data.get("public_id")
    if not new_public_id:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "public_id가 필요합니다.", "details": {}}
        }), 422

    boards = db["boards"]
    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    if str(board["owner_user_id"]) != str(user_id):
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "보드 생성자만 수정할 수 있습니다.", "details": {}}
        }), 403

    boards.update_one(
        {"_id": board["_id"]},
        {"$set": {"public_id": new_public_id, "updated_at": __import__("datetime").datetime.utcnow()}}
    )

    # TODO: board_invalidated WebSocket broadcast (기존 room)

    return jsonify({"public_id": new_public_id}), 200


# ---------------------------------------------------------------------------
# DELETE /api/boards/<public_id> - 보드 삭제
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>", methods=["DELETE"])
def delete_board(public_id: str):
    """
    보드 삭제 API
    - 인증: 필수 (보드 생성자만)
    - 처리: 스냅샷 저장 → notes 삭제 → board 삭제
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}
        }), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    boards = db["boards"]
    sticky_notes = db["sticky_notes"]
    snapshots = db["snapshots"]

    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    if str(board["owner_user_id"]) != str(user_id):
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "보드 생성자만 삭제할 수 있습니다.", "details": {}}
        }), 403

    now = __import__("datetime").datetime.utcnow()
    board_id = board["_id"]
    owner_id = board["owner_user_id"]

    # 1. 스냅샷 레코드 저장 (이미지 생성은 TODO, 레코드만 먼저 저장)
    try:
        snapshots.insert_one({
            "board_owner_id": owner_id,
            "image_key": "",  # TODO: 실제 스냅샷 이미지 저장
            "is_public": False,
            "created_at": now,
        })
    except Exception:
        return jsonify({
            "error": {"code": "INTERNAL_ERROR", "message": "스냅샷 저장에 실패했습니다.", "details": {}}
        }), 500

    # 2. notes 삭제
    sticky_notes.delete_many({"board_id": board_id})

    # 3. board 삭제
    boards.delete_one({"_id": board_id})

    # TODO: board_invalidated WebSocket broadcast

    return "", 204
