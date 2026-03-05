"""
보드 API 테스트.
"""
import io

import pytest

# 1x1 픽셀 PNG (유효한 이미지 파일)
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestCreateBoard:
    """POST /api/boards - 보드 생성"""

    def test_비인증_401(self, client):
        """인증 없이 요청 시 401"""
        res = client.post("/api/boards", json={"title": "테스트"})
        assert res.status_code == 401
        data = res.get_json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_인증_후_보드_생성_201(self, auth_client):
        """로그인 후 보드 생성 시 201, public_id 포함"""
        res = auth_client.post("/api/boards", json={"title": "내 칠판"})
        assert res.status_code == 201
        data = res.get_json()
        assert "public_id" in data
        assert data["title"] == "내 칠판"
        assert "owner_user_id" in data
        assert "created_at" in data

    def test_제목_없이_생성_201(self, auth_client):
        """title 생략 시 빈 문자열로 생성"""
        res = auth_client.post("/api/boards", json={})
        assert res.status_code == 201
        data = res.get_json()
        assert data["title"] == ""


class TestListBoards:
    """GET /api/boards - 내 보드 목록"""

    def test_비인증_401(self, client):
        """인증 없이 요청 시 401"""
        res = client.get("/api/boards")
        assert res.status_code == 401

    def test_인증_후_목록_200(self, auth_client):
        """로그인 후 목록 조회 시 200, boards 배열"""
        res = auth_client.get("/api/boards")
        assert res.status_code == 200
        data = res.get_json()
        assert "boards" in data
        assert "total" in data
        assert isinstance(data["boards"], list)


class TestGetBoard:
    """GET /api/boards/<public_id> - 보드 조회 (인증 불필요)"""

    def test_존재하지_않는_보드_404(self, client):
        """잘못된 public_id 시 404"""
        res = client.get("/api/boards/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404

    def test_보드_생성_후_조회_200(self, auth_client):
        """보드 생성 후 public_id로 조회 시 200, notes 포함"""
        create = auth_client.post("/api/boards", json={"title": "조회테스트"})
        assert create.status_code == 201
        public_id = create.get_json()["public_id"]

        res = auth_client.get(f"/api/boards/{public_id}")
        assert res.status_code == 200
        data = res.get_json()
        assert "board" in data
        assert "notes" in data
        assert data["board"]["public_id"] == public_id
        assert data["board"]["title"] == "조회테스트"


class TestCreateNote:
    """POST /api/boards/<public_id>/notes - 포스트잇 생성"""

    def test_비인증_401(self, client, auth_client):
        """인증 없이 요청 시 401"""
        # 보드 먼저 생성 (auth_client 사용)
        create = auth_client.post("/api/boards", json={"title": "노트테스트"})
        public_id = create.get_json()["public_id"]
        # 비인증 client로 포스트잇 생성 시도
        res = client.post(
            f"/api/boards/{public_id}/notes",
            json={"text": "안녕", "x": 0, "y": 0},
        )
        assert res.status_code == 401

    def test_포스트잇_생성_201(self, auth_client):
        """로그인 후 포스트잇 생성 시 201"""
        create = auth_client.post("/api/boards", json={"title": "노트테스트"})
        assert create.status_code == 201
        public_id = create.get_json()["public_id"]

        res = auth_client.post(
            f"/api/boards/{public_id}/notes",
            json={"text": "포스트잇 내용", "x": 100, "y": 200},
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data["text"] == "포스트잇 내용"
        assert data["x"] == 100
        assert data["y"] == 200
        assert "id" in data
        assert data["version"] == 0


class TestUploadImage:
    """POST /api/boards/<public_id>/images - 이미지 업로드"""

    def test_비인증_401(self, client, board_with_public_id):
        """인증 없이 업로드 시 401"""
        public_id = board_with_public_id
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        res = client.post(f"/api/boards/{public_id}/images", data=data)
        assert res.status_code == 401
        assert res.get_json()["error"]["code"] == "UNAUTHORIZED"

    def test_존재하지_않는_보드_404(self, auth_client):
        """유효하지 않은 public_id 시 404"""
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        res = auth_client.post(
            "/api/boards/00000000-0000-0000-0000-000000000000/images",
            data=data,
        )
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "BOARD_NOT_FOUND"

    def test_파일_없음_400(self, auth_client, board_with_public_id):
        """file 필드 없을 때 400"""
        res = auth_client.post(
            f"/api/boards/{board_with_public_id}/images",
            data={},
        )
        assert res.status_code == 400

    def test_빈_파일_400(self, auth_client, board_with_public_id):
        """파일명 없거나 빈 파일 시 400"""
        data = {"file": (io.BytesIO(b""), "")}
        res = auth_client.post(
            f"/api/boards/{board_with_public_id}/images",
            data=data,
        )
        assert res.status_code == 400

    def test_허용_확장자_아님_400(self, auth_client, board_with_public_id):
        """jpg, jpeg, png, gif 외 확장자 시 400"""
        data = {"file": (io.BytesIO(b"not an image"), "test.txt")}
        res = auth_client.post(
            f"/api/boards/{board_with_public_id}/images",
            data=data,
        )
        assert res.status_code == 400
        assert "VALIDATION_ERROR" in str(res.get_json())

    def test_업로드_성공_201(self, auth_client, board_with_public_id):
        """유효한 PNG 업로드 시 201, image_key와 url 반환"""
        public_id = board_with_public_id
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        res = auth_client.post(f"/api/boards/{public_id}/images", data=data)
        assert res.status_code == 201
        body = res.get_json()
        assert "image_key" in body
        assert "url" in body
        assert body["url"] == f"/api/boards/{public_id}/images/{body['image_key']}"
        assert body["image_key"].endswith(".png")


class TestGetImage:
    """GET /api/boards/<public_id>/images/<image_ref> - 이미지 조회"""

    def test_존재하지_않는_보드_404(self, client):
        """유효하지 않은 public_id 시 404"""
        res = client.get(
            "/api/boards/00000000-0000-0000-0000-000000000000/images/abc123.png"
        )
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "BOARD_NOT_FOUND"

    def test_노트에_없는_이미지_404(self, auth_client, board_with_public_id):
        """업로드만 하고 노트에 첨부 안 한 이미지 요청 시 404"""
        public_id = board_with_public_id
        # 업로드
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        up = auth_client.post(f"/api/boards/{public_id}/images", data=data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        # 노트 생성 없이 바로 이미지 조회 → 노트에 없으므로 404
        res = auth_client.get(f"/api/boards/{public_id}/images/{image_key}")
        # 또는 client (비인증)로 조회해도 404 (노트에 연결 안 됨)
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "IMAGE_NOT_FOUND"

    def test_이미지_조회_성공_200(self, auth_client, board_with_public_id):
        """업로드 후 노트에 첨부하면 이미지 조회 가능 (인증 불필요)"""
        public_id = board_with_public_id
        # 1. 업로드
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        up = auth_client.post(f"/api/boards/{public_id}/images", data=data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        # 2. 노트 생성 (image_key 포함)
        note = auth_client.post(
            f"/api/boards/{public_id}/notes",
            json={"text": "", "x": 0, "y": 0, "image_key": image_key},
        )
        assert note.status_code == 201
        assert note.get_json().get("image_url") == f"/api/boards/{public_id}/images/{image_key}"
        # 3. 이미지 조회 (비인증 client로 가능)
        res = auth_client.get(f"/api/boards/{public_id}/images/{image_key}")
        assert res.status_code == 200
        assert res.content_type.startswith("image/")
        assert res.data == MINIMAL_PNG_BYTES

    def test_비인증으로_이미지_조회_가능(self, auth_client, client, board_with_public_id):
        """이미지 조회는 인증 없이 가능"""
        public_id = board_with_public_id
        data = {"file": (io.BytesIO(MINIMAL_PNG_BYTES), "test.png")}
        up = auth_client.post(f"/api/boards/{public_id}/images", data=data)
        assert up.status_code == 201
        image_key = up.get_json()["image_key"]
        auth_client.post(
            f"/api/boards/{public_id}/notes",
            json={"text": "", "x": 0, "y": 0, "image_key": image_key},
        )
        # 비인증 client로 조회
        res = client.get(f"/api/boards/{public_id}/images/{image_key}")
        assert res.status_code == 200
        assert res.data == MINIMAL_PNG_BYTES
