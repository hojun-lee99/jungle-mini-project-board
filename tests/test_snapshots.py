"""
스냅샷 API 테스트.
"""
import io

import pytest

from flask_jwt_extended import create_access_token

# 1x1 픽셀 PNG (유효한 이미지 파일)
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestUploadSnapshot:
    """POST /api/snapshots - 스냅샷 이미지 업로드"""

    def test_비인증_401(self, client, board_with_public_id):
        """인증 없이 업로드 시 401"""
        public_id = board_with_public_id
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png"), "board_public_id": public_id}
        res = client.post("/api/snapshots", data=data)
        assert res.status_code == 401
        assert res.get_json()["error"]["code"] == "UNAUTHORIZED"

    def test_board_public_id_누락_400(self, auth_client):
        """board_public_id 없을 때 400"""
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        res = auth_client.post("/api/snapshots", data=data)
        assert res.status_code == 400
        assert "board_public_id" in res.get_json().get("error", {}).get("message", "")

    def test_존재하지_않는_보드_404(self, auth_client):
        """유효하지 않은 board_public_id 시 404"""
        data = {
            "file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png"),
            "board_public_id": "00000000-0000-0000-0000-000000000000",
        }
        res = auth_client.post("/api/snapshots", data=data)
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "BOARD_NOT_FOUND"

    def test_보드_생성자_아님_403(self, client, board_with_public_id):
        """다른 사용자 보드에 스냅샷 업로드 시 403"""
        public_id = board_with_public_id  # auth_client가 소유한 보드
        # 다른 사용자 생성
        res = client.post("/api/auth/register", json={"username": "other_user_12345", "password": "testpass"})
        assert res.status_code == 201
        other_user_id = res.get_json()["user_id"]
        token = create_access_token(identity=other_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png"), "board_public_id": public_id}
        res = client.post("/api/snapshots", data=data, headers=headers)
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "FORBIDDEN"

    def test_파일_없음_400(self, auth_client, board_with_public_id):
        """file 필드 없을 때 400"""
        data = {"board_public_id": board_with_public_id}
        res = auth_client.post("/api/snapshots", data=data)
        assert res.status_code == 400

    def test_업로드_성공_201(self, auth_client, board_with_public_id):
        """유효한 이미지 업로드 시 201, image_key 반환"""
        public_id = board_with_public_id
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png"), "board_public_id": public_id}
        res = auth_client.post("/api/snapshots", data=data)
        assert res.status_code == 201
        body = res.get_json()
        assert "image_key" in body
        assert body["image_key"].startswith("uploads/snapshots/")
        assert body["image_key"].endswith(".png")


class TestListMine:
    """GET /api/snapshots/mine - 내 스냅샷 목록"""

    def test_비인증_401(self, client):
        """인증 없이 조회 시 401"""
        res = client.get("/api/snapshots/mine")
        assert res.status_code == 401

    def test_빈_목록_200(self, auth_client):
        """스냅샷 없을 때 200, 빈 배열"""
        res = auth_client.get("/api/snapshots/mine")
        assert res.status_code == 200
        data = res.get_json()
        assert data["snapshots"] == []
        assert data["total"] == 0


class TestListPublic:
    """GET /api/snapshots/public - 공개 스냅샷 목록"""

    def test_비인증_가능_200(self, client):
        """인증 없이 조회 가능"""
        res = client.get("/api/snapshots/public")
        assert res.status_code == 200
        data = res.get_json()
        assert "snapshots" in data
        assert "total" in data


class TestGetSnapshotImage:
    """GET /api/snapshots/{id}/image - 스냅샷 이미지 조회"""

    def test_존재하지_않는_스냅샷_404(self, client):
        """유효하지 않은 snapshot_id 시 404"""
        res = client.get("/api/snapshots/000000000000000000000000/image")
        assert res.status_code == 404


class TestPatchSnapshot:
    """PATCH /api/snapshots/{id} - 공개 여부 토글"""

    def test_비인증_401(self, client):
        """인증 없이 PATCH 시 401"""
        res = client.patch("/api/snapshots/000000000000000000000000", json={"is_public": True})
        assert res.status_code == 401


class TestBoardDeleteWithSnapshot:
    """보드 삭제 + image_key → 스냅샷 레코드 생성 및 목록/이미지 조회"""

    def test_업로드_후_삭제_스냅샷_목록_조회(self, auth_client, board_with_public_id):
        """스냅샷 업로드 → 보드 삭제(image_key 포함) → 내 스냅샷 목록에 노출"""
        public_id = board_with_public_id
        # 1. 스냅샷 이미지 업로드
        upload_data = {
            "file": (io.BytesIO(MINIMAL_PNG_BYTES), "snap.png"),
            "board_public_id": public_id,
        }
        up = auth_client.post("/api/snapshots", data=upload_data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        # 2. 보드 삭제 (image_key 포함)
        del_res = auth_client.delete(
            f"/api/boards/{public_id}",
            json={"image_key": image_key},
            headers={"Content-Type": "application/json"},
        )
        assert del_res.status_code == 204
        # 3. 내 스냅샷 목록
        list_res = auth_client.get("/api/snapshots/mine")
        assert list_res.status_code == 200
        data = list_res.get_json()
        assert data["total"] == 1
        assert len(data["snapshots"]) == 1
        snap = data["snapshots"][0]
        assert "id" in snap
        assert "image_url" in snap
        assert snap["is_public"] is False
        # 4. 이미지 조회
        img_res = auth_client.get(snap["image_url"])
        assert img_res.status_code == 200
        assert img_res.content_type.startswith("image/")
        assert img_res.data == MINIMAL_PNG_BYTES

    def test_스냅샷_공개_토글_후_비인증_조회(self, client, auth_client, board_with_public_id):
        """스냅샷 공개 전환 후 비인증 사용자도 이미지 조회 가능"""
        public_id = board_with_public_id
        upload_data = {
            "file": (io.BytesIO(MINIMAL_PNG_BYTES), "snap.png"),
            "board_public_id": public_id,
        }
        up = auth_client.post("/api/snapshots", data=upload_data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        auth_client.delete(f"/api/boards/{public_id}", json={"image_key": image_key})
        list_res = auth_client.get("/api/snapshots/mine")
        snapshot_id = list_res.get_json()["snapshots"][0]["id"]
        # PATCH로 공개 전환
        patch_res = auth_client.patch(f"/api/snapshots/{snapshot_id}", json={"is_public": True})
        assert patch_res.status_code == 200
        # 비인증 client로 이미지 조회
        img_res = client.get(f"/api/snapshots/{snapshot_id}/image")
        assert img_res.status_code == 200
        assert img_res.data == MINIMAL_PNG_BYTES

    def test_비공개_스냅샷_타인_조회_403(self, client, auth_client, board_with_public_id):
        """비공개 스냅샷을 소유자가 아닌 사용자가 조회 시 403"""
        public_id = board_with_public_id
        upload_data = {
            "file": (io.BytesIO(MINIMAL_PNG_BYTES), "snap.png"),
            "board_public_id": public_id,
        }
        up = auth_client.post("/api/snapshots", data=upload_data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        auth_client.delete(f"/api/boards/{public_id}", json={"image_key": image_key})
        list_res = auth_client.get("/api/snapshots/mine")
        snapshot_id = list_res.get_json()["snapshots"][0]["id"]
        # 다른 사용자로 이미지 조회 시도
        other = client.post("/api/auth/register", json={"username": "other_snap_12345", "password": "test"})
        assert other.status_code == 201
        token = create_access_token(identity=other.get_json()["user_id"])
        img_res = client.get(
            f"/api/snapshots/{snapshot_id}/image",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert img_res.status_code == 403
