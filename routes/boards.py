"""
보드 관련 API 라우트
- 보드 생성 (POST /api/boards)
- 내 보드 목록 (GET /api/boards)
- 보드 조회 (GET /api/boards/<public_id>)
- 보드 public_id 변경 (PATCH /api/boards/<public_id>)
- 보드 삭제 (DELETE /api/boards/<public_id>)
- 포스트잇 생성 (POST /api/boards/<public_id>/notes)
- 포스트잇 수정/이동 (PATCH /api/boards/<public_id>/notes/<note_id>)
- 포스트잇 삭제 (DELETE /api/boards/<public_id>/notes/<note_id>)
"""
import uuid

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from pymongo import ReturnDocument
from utils import utc_now

boards_bp = Blueprint("boards", __name__, url_prefix="/api/boards")


def _get_current_user_id():
    """JWT 쿠키에서 현재 로그인 사용자 ID 반환."""
    return get_jwt_identity()


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
@jwt_required(optional=True)
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

    now = utc_now()
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
@jwt_required(optional=True)
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
@jwt_required(optional=True)
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
        {"$set": {"public_id": new_public_id, "updated_at": utc_now()}}
    )

    # TODO: board_invalidated WebSocket broadcast (기존 room)

    return jsonify({"public_id": new_public_id}), 200


# ---------------------------------------------------------------------------
# DELETE /api/boards/<public_id> - 보드 삭제
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>", methods=["DELETE"])
@jwt_required(optional=True)
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

    now = utc_now()
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


# ---------------------------------------------------------------------------
# POST /api/boards/<public_id>/notes - 포스트잇 생성
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>/notes", methods=["POST"])
@jwt_required(optional=True)
def create_note(public_id: str):
    """
    포스트잇 생성 API
    - 인증: 필수
    - 보드당 300개 제한
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

    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    board_id = board["_id"]
    data = request.get_json(silent=True) or {}

    text = data.get("text") or ""
    if len(text) > 500:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "text는 500자를 초과할 수 없습니다.", "details": {}}
        }), 422

    image_key = data.get("image_key") or ""
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))

    # 300개 제한: note_count < 300 조건부 $inc
    result = boards.find_one_and_update(
        {"_id": board_id, "note_count": {"$lt": 300}},
        {"$inc": {"note_count": 1, "next_z_index": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not result:
        return jsonify({
            "error": {"code": "NOTE_LIMIT_EXCEEDED", "message": "보드당 포스트잇 최대 300개 제한을 초과했습니다.", "details": {}}
        }), 403

    z_index = result["next_z_index"]

    now = utc_now()
    note_doc = {
        "board_id": board_id,
        "owner_user_id": user_id,
        "text": text,
        "image_key": image_key,
        "x": x,
        "y": y,
        "z_index": z_index,
        "version": 0,
        "created_at": now,
        "updated_at": now,
    }
    ins = sticky_notes.insert_one(note_doc)
    note_doc["_id"] = ins.inserted_id

    image_base_url = current_app.config.get("IMAGE_BASE_URL") or ""
    return jsonify(_serialize_note(note_doc, image_base_url)), 201


# ---------------------------------------------------------------------------
# PATCH /api/boards/<public_id>/notes/<note_id> - 포스트잇 수정/이동
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>/notes/<note_id>", methods=["PATCH"])
@jwt_required(optional=True)
def update_note(public_id: str, note_id: str):
    """
    포스트잇 수정/이동 API
    - 인증: 필수 (보드 생성자 또는 포스트잇 작성자)
    - 낙관적 락 (version)
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
    version = data.get("version")
    if version is None:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "version이 필요합니다.", "details": {}}
        }), 422

    # NO_CHANGES: version만 있고 변경 필드 없음
    change_keys = {"text", "image_key", "x", "y"}
    has_change = any(k in data for k in change_keys)
    if not has_change:
        return jsonify({
            "error": {"code": "NO_CHANGES", "message": "변경할 필드가 없습니다.", "details": {}}
        }), 400

    boards = db["boards"]
    sticky_notes = db["sticky_notes"]

    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    try:
        oid = ObjectId(note_id)
    except Exception:
        return jsonify({
            "error": {"code": "NOTE_NOT_FOUND", "message": "포스트잇을 찾을 수 없습니다.", "details": {}}
        }), 404

    note = sticky_notes.find_one({"_id": oid, "board_id": board["_id"]})
    if not note:
        return jsonify({
            "error": {"code": "NOTE_NOT_FOUND", "message": "포스트잇을 찾을 수 없습니다.", "details": {}}
        }), 404

    is_owner = str(note["owner_user_id"]) == str(user_id)
    is_board_owner = str(board["owner_user_id"]) == str(user_id)
    if not is_owner and not is_board_owner:
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "수정 권한이 없습니다.", "details": {}}
        }), 403

    if note.get("version", 0) != version:
        return jsonify({
            "error": {"code": "CONFLICT", "message": "버전 충돌. 최신 데이터를 확인해주세요.", "details": {}}
        }), 409

    # update payload
    update = {"$set": {"updated_at": utc_now(), "version": version + 1}}
    if "text" in data:
        if len(str(data["text"])) > 500:
            return jsonify({
                "error": {"code": "VALIDATION_ERROR", "message": "text는 500자를 초과할 수 없습니다.", "details": {}}
            }), 422
        update["$set"]["text"] = data["text"]
    if "image_key" in data:
        update["$set"]["image_key"] = data["image_key"] if data["image_key"] is not None else ""
    if "x" in data:
        update["$set"]["x"] = int(data["x"])
    if "y" in data:
        update["$set"]["y"] = int(data["y"])

    # z_index: boards.next_z_index 사용
    result = boards.find_one_and_update(
        {"_id": board["_id"]},
        {"$inc": {"next_z_index": 1}},
        return_document=ReturnDocument.AFTER,
    )
    new_z = result["next_z_index"]
    update["$set"]["z_index"] = new_z

    up = sticky_notes.update_one(
        {"_id": oid, "board_id": board["_id"], "version": version},
        update,
    )
    if up.matched_count == 0:
        return jsonify({
            "error": {"code": "CONFLICT", "message": "버전 충돌. 최신 데이터를 확인해주세요.", "details": {}}
        }), 409

    updated = sticky_notes.find_one({"_id": oid})
    image_base_url = current_app.config.get("IMAGE_BASE_URL") or ""
    return jsonify(_serialize_note(updated, image_base_url)), 200


# ---------------------------------------------------------------------------
# DELETE /api/boards/<public_id>/notes/<note_id> - 포스트잇 삭제
# ---------------------------------------------------------------------------
@boards_bp.route("/<public_id>/notes/<note_id>", methods=["DELETE"])
@jwt_required(optional=True)
def delete_note(public_id: str, note_id: str):
    """
    포스트잇 삭제 API
    - 인증: 필수 (보드 생성자 또는 포스트잇 작성자)
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

    board = boards.find_one({"public_id": public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    try:
        oid = ObjectId(note_id)
    except Exception:
        return jsonify({
            "error": {"code": "NOTE_NOT_FOUND", "message": "포스트잇을 찾을 수 없습니다.", "details": {}}
        }), 404

    note = sticky_notes.find_one({"_id": oid, "board_id": board["_id"]})
    if not note:
        return jsonify({
            "error": {"code": "NOTE_NOT_FOUND", "message": "포스트잇을 찾을 수 없습니다.", "details": {}}
        }), 404

    is_owner = str(note["owner_user_id"]) == str(user_id)
    is_board_owner = str(board["owner_user_id"]) == str(user_id)
    if not is_owner and not is_board_owner:
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "삭제 권한이 없습니다.", "details": {}}
        }), 403

    sticky_notes.delete_one({"_id": oid, "board_id": board["_id"]})
    boards.update_one({"_id": board["_id"]}, {"$inc": {"note_count": -1}})

    return "", 204
