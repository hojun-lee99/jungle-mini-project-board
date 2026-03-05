"""
스냅샷 API
- POST /api/snapshots - 보드 삭제 직전 클라이언트 캡처 이미지 업로드 (image_key 반환)
- GET /api/snapshots/mine - 내 스냅샷 목록
- GET /api/snapshots/public - 공개 스냅샷 목록
- GET /api/snapshots/<id>/image - 스냅샷 이미지 조회
- PATCH /api/snapshots/<id> - 공개/비공개 토글
"""
import os
import uuid

import boto3

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from botocore.exceptions import ClientError

from utils import utc_now

snapshots_bp = Blueprint("snapshots", __name__, url_prefix="/api/snapshots")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif"}
MAX_SIZE = 5 * 1024 * 1024  # 5MB (스냅샷은 보드 전체이므로 포스트잇 이미지보다 큼)
EXT_TO_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif"}


def _get_current_user_id():
    return get_jwt_identity()


# ---------------------------------------------------------------------------
# POST /api/snapshots - 스냅샷 이미지 업로드 (삭제 직전 클라이언트 캡처용)
# ---------------------------------------------------------------------------
@snapshots_bp.route("", methods=["POST"])
@jwt_required(optional=True)
def upload_snapshot():
    """
    보드 삭제 직전 클라이언트(html2canvas 등)가 캡처한 이미지 업로드.
    반환된 image_key를 DELETE /api/boards/{public_id} 요청 본문에 포함하여 전달.
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}}), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    board_public_id = request.form.get("board_public_id")
    if not board_public_id:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "board_public_id가 필요합니다.", "details": {}}
        }), 400

    board = db["boards"].find_one({"public_id": board_public_id})
    if not board:
        return jsonify({
            "error": {"code": "BOARD_NOT_FOUND", "message": "유효하지 않은 보드 링크입니다.", "details": {}}
        }), 404

    if str(board["owner_user_id"]) != str(user_id):
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "보드 생성자만 스냅샷을 생성할 수 있습니다.", "details": {}}
        }), 403

    if "file" not in request.files:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "이미지 파일이 필요합니다.", "details": {}}
        }), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "파일을 선택해 주세요.", "details": {}}
        }), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "jpg, jpeg, png, gif만 업로드 가능합니다.", "details": {}}
        }), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_SIZE:
        return jsonify({
            "error": {"code": "VALIDATION_ERROR", "message": "스냅샷 이미지는 5MB 이하여야 합니다.", "details": {}}
        }), 400

    owner_id = str(board["owner_user_id"])
    filename = f"{uuid.uuid4().hex}{ext}"
    # app.config 우선. ''로 명시하면 S3 미사용 (테스트 시 로컬 저장)
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if bucket is None:
        bucket = os.environ.get("S3_BUCKET_NAME") or ""

    if bucket:
        # S3 업로드
        region = current_app.config.get("AWS_REGION", "ap-northeast-2")
        s3 = boto3.client("s3", region_name=region)
        key = f"snapshots/{owner_id}/{filename}"
        try:
            file.seek(0)
            s3.upload_fileobj(
                file, bucket, key, ExtraArgs={"ContentType": EXT_TO_MIME.get(ext, "image/png")}
            )
        except ClientError as e:
            current_app.logger.exception("S3 upload failed: %s", e)
            return jsonify({
                "error": {"code": "INTERNAL_ERROR", "message": "스냅샷 업로드에 실패했습니다.", "details": {}}
            }), 500
        image_key = key
    else:
        # 로컬 저장 (fallback)
        base_dir = current_app.static_folder or "static"
        upload_dir = os.path.join(base_dir, "uploads", "snapshots", owner_id)
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        image_key = f"uploads/snapshots/{owner_id}/{filename}"

    return jsonify({"image_key": image_key}), 201

# *** Todo: 이하 내용은 스냅샷 게시판에 필요한 api 초안입니다. 필요시 수정해서 사용하세요. ***

# ---------------------------------------------------------------------------
# GET /api/snapshots/mine - 내 스냅샷 목록
# ---------------------------------------------------------------------------
@snapshots_bp.route("/mine", methods=["GET"])
@jwt_required()
def list_mine():
    """나에게 귀속된 보드 스냅샷 목록."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}}), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    skip = (page - 1) * limit

    snapshots = db["snapshots"]
    total = snapshots.count_documents({"board_owner_id": user_id})
    cursor = snapshots.find({"board_owner_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    items = list(cursor)

    def _serialize(doc):
        return {
            "id": str(doc["_id"]),
            "title": doc.get("title", ""),  
            "image_url": f"/api/snapshots/{doc['_id']}/image",
            "is_public": doc.get("is_public", False),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        }

    return jsonify({"snapshots": [_serialize(d) for d in items], "total": total}), 200


# ---------------------------------------------------------------------------
# GET /api/snapshots/public - 공개 스냅샷 목록
# ---------------------------------------------------------------------------
@snapshots_bp.route("/public", methods=["GET"])
def list_public():
    """모든 사용자가 공개한 스냅샷 목록."""
    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    skip = (page - 1) * limit

    snapshots = db["snapshots"]
    users = db["users"]
    total = snapshots.count_documents({"is_public": True})
    cursor = snapshots.find({"is_public": True}).sort("created_at", -1).skip(skip).limit(limit)
    items = list(cursor)

    owner_ids = list({str(d["board_owner_id"]) for d in items})
    user_map = {}
    if owner_ids:
        for u in users.find({"user_id": {"$in": owner_ids}}):
            user_map[str(u["user_id"])] = u.get("username", "")

    def _serialize(doc):
        return {
            "id": str(doc["_id"]),
            "title": doc.get("title", ""),  
            "image_url": f"/api/snapshots/{doc['_id']}/image",
            "owner_username": user_map.get(str(doc["board_owner_id"]), ""),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        }

    return jsonify({"snapshots": [_serialize(d) for d in items], "total": total}), 200


# ---------------------------------------------------------------------------
# GET /api/snapshots/<id>/image - 스냅샷 이미지 조회
# ---------------------------------------------------------------------------
@snapshots_bp.route("/<snapshot_id>/image", methods=["GET"])
@jwt_required(optional=True)
def get_snapshot_image(snapshot_id: str):
    """스냅샷 이미지 반환. 소유자 또는 공개된 경우만 허용."""
    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    try:
        oid = ObjectId(snapshot_id)
    except Exception:
        return jsonify({
            "error": {"code": "SNAPSHOT_NOT_FOUND", "message": "스냅샷을 찾을 수 없습니다.", "details": {}}
        }), 404

    snap = db["snapshots"].find_one({"_id": oid})
    if not snap:
        return jsonify({
            "error": {"code": "SNAPSHOT_NOT_FOUND", "message": "스냅샷을 찾을 수 없습니다.", "details": {}}
        }), 404

    user_id = _get_current_user_id()
    owner_id = str(snap["board_owner_id"])
    is_public = snap.get("is_public", False)

    if not is_public and str(user_id) != owner_id:
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "접근 권한이 없습니다.", "details": {}}
        }), 403

    image_key = snap.get("image_key")
    if not image_key:
        return jsonify({
            "error": {"code": "IMAGE_NOT_FOUND", "message": "이미지가 없습니다.", "details": {}}
        }), 404

    # app.config 우선. ''로 명시하면 S3 미사용 (테스트 시 로컬 저장)
    bucket = current_app.config.get("S3_BUCKET_NAME")
    if bucket is None:
        bucket = os.environ.get("S3_BUCKET_NAME") or ""

    if bucket and not image_key.startswith("uploads/"):
        # S3에서 스트리밍
        region = current_app.config.get("AWS_REGION", "ap-northeast-2")
        s3 = boto3.client("s3", region_name=region)
        try:
            obj = s3.get_object(Bucket=bucket, Key=image_key)
            body = obj["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return jsonify({
                    "error": {"code": "IMAGE_NOT_FOUND", "message": "이미지 파일을 찾을 수 없습니다.", "details": {}}
                }), 404
            raise
        ext = os.path.splitext(image_key)[1].lower()
        mimetype = EXT_TO_MIME.get(ext, "application/octet-stream")
        return current_app.response_class(body, mimetype=mimetype)

    # 로컬 파일
    base_dir = current_app.static_folder or "static"
    filepath = os.path.join(base_dir, image_key)
    if not os.path.isfile(filepath):
        return jsonify({
            "error": {"code": "IMAGE_NOT_FOUND", "message": "이미지 파일을 찾을 수 없습니다.", "details": {}}
        }), 404
    ext = os.path.splitext(image_key)[1].lower()
    mimetype = EXT_TO_MIME.get(ext, "application/octet-stream")
    return send_file(filepath, mimetype=mimetype)


# ---------------------------------------------------------------------------
# PATCH /api/snapshots/<id> - 공개/비공개 토글
# ---------------------------------------------------------------------------
@snapshots_bp.route("/<snapshot_id>", methods=["PATCH"])
@jwt_required()
def update_snapshot(snapshot_id: str):
    """스냅샷 공개 여부 토글. 소유자만 가능."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요합니다.", "details": {}}}), 401

    db = getattr(current_app, "db", None)
    if db is None:
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "DB not configured."}}), 500

    try:
        oid = ObjectId(snapshot_id)
    except Exception:
        return jsonify({
            "error": {"code": "SNAPSHOT_NOT_FOUND", "message": "스냅샷을 찾을 수 없습니다.", "details": {}}
        }), 404

    snap = db["snapshots"].find_one({"_id": oid})
    if not snap:
        return jsonify({
            "error": {"code": "SNAPSHOT_NOT_FOUND", "message": "스냅샷을 찾을 수 없습니다.", "details": {}}
        }), 404

    if str(snap["board_owner_id"]) != str(user_id):
        return jsonify({
            "error": {"code": "FORBIDDEN", "message": "스냅샷 소유자만 수정할 수 있습니다.", "details": {}}
        }), 403

    data = request.get_json(silent=True) or {}
    new_is_public = data.get("is_public")
    if new_is_public is None:
        # 토글: 현재 값의 반대
        new_is_public = not snap.get("is_public", False)

    db["snapshots"].update_one({"_id": oid}, {"$set": {"is_public": bool(new_is_public)}})
    return jsonify({"id": str(oid), "is_public": new_is_public}), 200
