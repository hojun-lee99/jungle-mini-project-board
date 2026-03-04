# 비즈니스 로직과 db 접근과 관련된 코드 작성
from pymongo import MongoClient
from config import Config
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

#!!! 
# 로컬 db 설정에 맞춰 수정 필요
client = MongoClient(Config.MONGO_URI)
db = client['jungle_db']

# 401 아이디 비밀번호 불일치
def login_user(data):
  username = data.get('username')
  password = data.get('password')

  if not username or not password:
    return {"error": "username과 password는 필수 입력값입니다."}, 422
  
  user = db.users.find_one({"username": username})

  if not user or not check_password_hash(user['password'], password):
    return {"error": "아이디 또는 비밀번호가 일치하지 않습니다."}, 401
  
  return {
    "user_id": user["user_id"],
    "username": user["username"]
  }, 200



def register_user(data):
  username = data.get('username')
  password = data.get('password')

  if not username or not password:
    return {"error": "username과 password는 필수 입력값입니다."}, 422
  
  if type(username) is not str or type(password) is not str:
    return {"error": "잘못된 데이터 형식입니다."}, 422
  
  if db.users.find_one({"username": username}):
    return {"error": "이미 존재하는 username입니다."}, 400
  
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