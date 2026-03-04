from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins=['http://localhost:5001'], manage_session=False)