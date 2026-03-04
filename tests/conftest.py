"""
pytest 공통 fixtures.
MongoClient를 mongomock으로 치환한 뒤 app을 import.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mongomock
import pymongo

# app import 전에 MongoClient를 mongomock으로 치환
pymongo.MongoClient = mongomock.MongoClient

import uuid

import pytest

from app import app
from flask_jwt_extended import create_access_token


@pytest.fixture
def client():
    """Flask 테스트 클라이언트."""
    app.config["TESTING"] = True
    # 테스트에서 헤더로도 JWT 전달 가능하도록 설정
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client(client):
    """
    로그인된 상태의 테스트 클라이언트.
    회원가입 후 JWT를 Authorization 헤더에 담아 요청하는 client 반환.
    (테스트 클라이언트의 쿠키 전달 이슈를 피하기 위해 헤더 사용)
    """
    # 테스트마다 고유 사용자 생성 (mongomock 데이터 공유로 중복 방지)
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    res = client.post(
        "/api/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert res.status_code == 201
    user_id = res.get_json()["user_id"]

    token = create_access_token(identity=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # 헤더를 기본으로 포함하는 래퍼 반환
    class AuthClient:
        def get(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(headers)
            return client.get(url, **kwargs)

        def post(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(headers)
            return client.post(url, **kwargs)

        def patch(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(headers)
            return client.patch(url, **kwargs)

        def delete(self, url, **kwargs):
            kwargs.setdefault("headers", {}).update(headers)
            return client.delete(url, **kwargs)

    return AuthClient()
