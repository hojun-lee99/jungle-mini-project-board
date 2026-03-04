from flask import Flask, render_template
from pymongo import MongoClient

from routes.boards import boards_bp

app = Flask(__name__)

# !!! 로컬 db 설정에 맞춰 수정 필요
client = MongoClient("mongodb://localhost:27017")
db = client["mydb"]
app.db = db  # Blueprint에서 current_app.db로 접근

# Blueprint 등록
app.register_blueprint(boards_bp)


@app.route('/')
def home():
  return render_template('index.html')

if __name__ == '__main__':  
  app.run('0.0.0.0', port=5001, debug=True)