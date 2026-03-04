from flask import Flask, make_response, render_template, jsonify, request
from flask_cors import CORS
from config import Config
from services import register_user, login_user
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
)
from datetime import timedelta
from pymongo import MongoClient
from routes.boards import boards_bp
from extensions import socketio
import sockets

app = Flask(__name__)
CORS(app, supports_credentials=True)

app.config["JWT_SECRET_KEY"] = Config.SECRET_KEY
app.config["JWT_TOKEN_LOCATION"] = ['cookies']
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)
# !!! 로컬 db 설정에 맞춰 수정 필요
client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]
app.db = db  # Blueprint에서 current_app.db로 접근

socketio.init_app(app)

# Blueprint 등록
app.register_blueprint(boards_bp)




@app.route('/')
def home():
    return render_template('login.html')


@app.route('/main')
def main():
    """로그인 후 내 보드 목록 페이지."""
    return render_template('main.html')


@app.route('/boards/<public_id>')
def board_page(public_id: str):
    """칠판(화이트보드) 페이지. 보드 및 포스트잇 렌더링."""
    return render_template('board.html', public_id=public_id)

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


@app.route("/api/auth/logout", methods=["POST"])
@jwt_required()
def api_logout():
    """세션(JWT 쿠키) 무효화. 204 No Content 반환."""
    response = make_response("", 204)
    unset_jwt_cookies(response)
    return response


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json()

    if not data:
      return jsonify({"error": "요청 본문(Body)이 비어있습니다."}), 422
    
    response_data, statuscode = register_user(data)

    return jsonify(response_data), statuscode

if __name__ == '__main__':  
  socketio.run('0.0.0.0', port=5001, debug=True)