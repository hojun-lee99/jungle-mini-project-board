# 비즈니스 로직과 db 접근과 관련된 코드 작성
from pymongo import MongoClient
from config import Config
import uuid
from werkzeug.security import generate_password_hash

#!!! 
# 로컬 db 설정에 맞춰 수정 필요
client = MongoClient(Config.MONGO_URI)
db = client['jungle_db']

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