"""
보드 API 테스트.
"""
import pytest


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
