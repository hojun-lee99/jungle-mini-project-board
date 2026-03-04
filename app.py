from flask import Flask, render_template, jsonify, request
from services import register_user

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json()

    if not data:
      return jsonify({"error": "요청 본문(Body)이 비어있습니다."}), 422
    
    response_data, statuscode = register_user(data)

    return jsonify(response_data), statuscode

if __name__ == '__main__':  
  app.run('0.0.0.0', port=5001, debug=True)