from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from config import Config
from services import register_user, login_user
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies 
from datetime import timedelta
from pymongo import MongoClient

from routes.boards import boards_bp

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = Config.SECRET_KEY
app.config["JWT_TOKEN_LOCATION"] = ['cookies']
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)
# !!! 로컬 db 설정에 맞춰 수정 필요
client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]
app.db = db  # Blueprint에서 current_app.db로 접근

# Blueprint 등록
app.register_blueprint(boards_bp)


@app.route('/')
def home():
    return render_template('index.html')

# 일단은 access token만 httponly로 발급 시간이 된다면 refresh token도 발급
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    
    if not data:
      return jsonify({"error": "요청 본문(Body)이 비어있습니다."}), 422

    user_data, statuscode = login_user(data)
    
    if statuscode != 200:
      return jsonify(user_data), statuscode

    access_token = create_access_token(identity=user_data['user_id'])

    response = jsonify({
      "user_id": user_data['user_id'],
      "username": user_data['username']
    })

    set_access_cookies(response, access_token)

    return response, statuscode


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json()

    if not data:
      return jsonify({"error": "요청 본문(Body)이 비어있습니다."}), 422
    
    response_data, statuscode = register_user(data)

    return jsonify(response_data), statuscode

if __name__ == '__main__':  
  app.run('0.0.0.0', port=5001, debug=True)