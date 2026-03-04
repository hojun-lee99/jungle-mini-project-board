# 실시간 동시 접속 아키텍처 설계 (최대 100명 대응)

## 1. 목적

본 문서는 하나의 보드에 최대 100명이 동시에 접속하는 상황을 안전하게 처리하기 위한 최소·안전 아키텍처를 정의한다.

시스템은 다음을 만족해야 한다:

- 실시간 동기화 유지
- 데이터 정합성 보장
- 서버 부하 최소화
- 3일 프로젝트 범위 내 구현 가능

---

## 2. 기술 스택

- Backend: Flask
- WebSocket: Flask-SocketIO
- Async Engine: eventlet
- Database: MongoDB
- 배포: 단일 EC2 인스턴스

---

## 3. 핵심 설계 원칙

### WebSocket은 전파(브로드캐스트) 용도이다.
### 데이터 정합성은 HTTP + 낙관적 락으로 보장한다.

모든 데이터 변경은 반드시 다음 순서를 따른다:

1. HTTP 요청 (PATCH / POST / DELETE)
2. version 검증
3. DB 업데이트
4. 업데이트 성공 이후 WebSocket broadcast

WebSocket을 통해 직접 DB 상태를 변경하지 않는다.

---

## 4. 보드 단위 Room 분리 (필수)

각 보드는 고유한 `public_id`를 가진다.

WebSocket 연결 시:

```python
join_room(f"board_{public_id}")
```

모든 이벤트 전파는 해당 room으로만 전송한다:

```python
socketio.emit(
    "note_updated",
    note_data,
    room=f"board_{public_id}"
)
```

이 방식은 다음을 보장한다:
- 다른 보드 사용자에게 이벤트 전파 방지
- 네트워크 부하 감소
- 확장성 확보

---

## 5. 이벤트 설계

이벤트는 최소 3종류만 사용한다.

| 이벤트명	| 설명 | 
| note_created	| 포스트잇 생성 | 
| note_updated	| 포스트잇 수정 또는 이동 | 
| note_deleted	| 포스트잇 삭제 | 

보드 전체 데이터를 재전송하지 않는다.
변경된 포스트잇 데이터만 전송한다.

---

## 6. 수정 처리 흐름

포스트잇 수정 시

1. Client → HTTP PATCH (version 포함)

2. Server:
 - version 검증
 - 불일치 시 409 반환 (broadcast 없음)
 - 일치 시 DB 업데이트

3. DB 업데이트 성공

4. WebSocket broadcast (note_updated)

---

## 7. 100명 동시 접속 대응 전략

### 7.1 연결 유지 전략

- eventlet 기반 비동기 처리
- WebSocket persistent connection 유지
- Idle 연결은 CPU 사용 거의 없음
- 100개의 동시 연결은 일반적인 EC2 인스턴스에서 충분히 처리 가능하다. 

### 7.2 트래픽 최소화 전략

다음을 금지한다:
- drag 중간 단계에서 PATCH 전송
- 보드 전체 JSON 재전송
- 주기적 전체 동기화

권장 방식:
- drag 종료 시점에만 PATCH
- 저장 버튼 클릭 시에만 PATCH
- 1 요청 = 1 broadcast

### 7.3 Broadcast 범위 제한

항상 board room으로만 broadcast한다.
전역 broadcast는 금지한다.

---

## 8. 충돌 처리 전략

낙관적 락은 필수이다.

version 충돌 발생 시:
- 409 반환
- WebSocket 이벤트 발생하지 않음
- 클라이언트는 최신 데이터 재조회

WebSocket은 정합성을 보장하지 않는다.
정합성은 HTTP + version 검증으로 보장한다.

---

## 9. 부하 시나리오 분석
1) 100명 접속 중 1명 수정
- PATCH 1회
- DB update 1회
- broadcast 1회
- 99명에게 소형 JSON 전송
- 부하 매우 낮음.

2) 10명이 동시에 수정
- PATCH 10회
- 일부 version 충돌 가능
- 충돌 요청은 broadcast 없음
- 정상 요청만 전파

정합성 유지 가능.

---

## 10. 설계 한계

본 설계는 다음 조건에서 안전하다:

- 단일 서버 인스턴스
- 단일 프로세스
- 보드당 최대 100명
- 과도한 burst 이벤트 없음

수천 명 이상 확장이 필요할 경우:
- Redis message broker
- Multi-worker 구성
- 수평 확장 구조 필요

그러나 본 미니 프로젝트 범위에서는 필요하지 않다.

---

## 11. 결론

100명 동시 접속을 안전하게 처리하기 위한 최소 설계는 다음과 같다:
1. Flask-SocketIO + eventlet 사용
2. 보드별 room 분리
3. HTTP + 낙관적 락으로 정합성 보장
4. DB 업데이트 성공 이후에만 WebSocket broadcast
5. 변경된 데이터만 전송

이 구조는 안정성과 구현 난이도 사이의 균형을 유지하면서 프로젝트 범위 내에서 현실적으로 구현 가능한 방식이다.