from flask_socketio import SocketIO

#! 로컬 개발용으로 모든 출처허용 배포시 수정 필요!
socketio = SocketIO(cors_allowed_origins='*', manage_session=False)