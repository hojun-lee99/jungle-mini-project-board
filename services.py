# 비즈니스 로직과 db 접근과 관련된 코드 작성
import re
from pymongo import MongoClient
from config import Config
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

# 회원가입 허용 문자: username=영문대소문자/숫자/한글/_, password=영문대소문자/숫자/!@#$%^&*()-
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9가-힣_]+$")
PASSWORD_PATTERN = re.compile(r"^[a-zA-Z0-9!@#$%^&*()\-_]+$")

#!!! 
# 로컬 db 설정에 맞춰 수정 필요
client = MongoClient(Config.MONGO_URI)
db = client['jungle_db']

# 401 아이디 비밀번호 불일치
def login_user(data):
  username = data.get('username')
  password = data.get('password')

  if not username or not password:
    return {"error": "이름과 비밀번호는 필수 입력값입니다."}, 422
  
  user = db.users.find_one({"username": username})

  if not user or not check_password_hash(user['password'], password):
    return {"error": "이름 또는 비밀번호가 일치하지 않습니다."}, 401
  
  return {
    "user_id": user["user_id"],
    "username": user["username"]
  }, 200



def register_user(data):
  username = data.get('username')
  password = data.get('password')

  if not username or not password:
    return {"error": "이름과 비밀번호는 필수 입력값입니다."}, 422
  
  if type(username) is not str or type(password) is not str:
    return {"error": "잘못된 데이터 형식입니다."}, 422

  if len(username) < 2 or len(username) > 20:
    return {"error": "이름은 2자 이상 20자 이하로 입력해주세요."}, 422

  if not USERNAME_PATTERN.fullmatch(username):
    return {"error": "이름은 영문 대소문자, 숫자, 한글만 사용 가능합니다."}, 422

  if len(password) < 8 or len(password) > 50:
    return {"error": "비밀번호는 8자 이상 50자 이하로 입력해주세요."}, 422

  if not PASSWORD_PATTERN.fullmatch(password):
    return {"error": "비밀번호는 영문 대소문자, 숫자, !@#$%^&*()-_ 만 사용 가능합니다."}, 422
  
  if db.users.find_one({"username": username}):
    return {"error": "이미 존재하는 이름입니다."}, 400
  
  user_id = str(uuid.uuid4())
  hased_pw = generate_password_hash(password)

  new_user = {
    "user_id": user_id,
    "username": username,
    "password": hased_pw
  }

  db.users.insert_one(new_user)

  return {
    "user_id": user_id,
    "username": username
  }, 201


def create_test_user():
  """
  UI 없이 테스트 사용자(test/test)를 생성합니다.
  이미 존재하면 아무 작업도 하지 않습니다.
  """
  username = "test"
  password = "test"

  if db.users.find_one({"username": username}):
    return {"message": f"사용자 '{username}'가 이미 존재합니다.", "created": False}

  user_id = str(uuid.uuid4())
  hashed_pw = generate_password_hash(password)
  db.users.insert_one({
    "user_id": user_id,
    "username": username,
    "password": hashed_pw
  })
  return {"message": f"사용자 '{username}' 생성 완료", "created": True}