# sockets.py
from flask import request
from flask_socketio import ConnectionRefusedError, join_room, emit
from flask_jwt_extended import decode_token
from extensions import socketio

@socketio.on('connect')
def handle_connect():
    """
    연결 및 인증 (Handshake)
    클라이언트가 연결을 시도할 때 쿠키에 있는 JWT를 검사합니다.
    """
    token = request.cookies.get('access_token_cookie')
    
    if not token:
        raise ConnectionRefusedError('authentication_required')
    
    try:
        decode_token(token)
        print("웹소켓 인증 성공 및 연결됨!")
    except Exception:
        raise ConnectionRefusedError('authentication_required')

@socketio.on('join_board')
def on_join_board(data):
    """
    클라이언트가 연결 후 특정 보드(칠판) 방에 입장시켜 달라고 요청할 때 실행됩니다.
    """
    public_id = data.get('public_id')
    if public_id:
        room_name = f"board_{public_id}"
        join_room(room_name)
        print(f"[{room_name}] 방에 유저가 입장했습니다.")

@socketio.on('move_note')
def on_move_note(data):
    public_id = data.get('public_id')
    if public_id:
        room_name = f"board_{public_id}"

        emit('note_moved', data, room=room_name, include_self=False)

@socketio.on('create_note')
def on_create_note(data):
    public_id = data.get('public_id')
    if public_id:
        room_name = f"board_{public_id}"
        print(room_name)
        emit('note_created', data, room=room_name, include_self=False)

@socketio.on('delete_note')
def on_delete_note(data):
    public_id = data.get('public_id')
    if public_id:
        room_name = f"board_{public_id}"

        emit('note_deleted', data, room=room_name, include_self=False)
