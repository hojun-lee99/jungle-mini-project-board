# 시스템 아키텍처 설계 문서 (v2)
## Jungle Whiteboard

---

# 1. 설계 목표

본 문서는 요구사항 정의서(v2)를 기반으로 Jungle Whiteboard의 전체 시스템 아키텍처를 정의한다.

설계 목표:

- public_id 기반 접근 제어
- 100명 동시 접속 지원
- 낙관적 락 기반 정합성 보장
- WebSocket 기반 실시간 동기화
- MongoDB 기반 단순·안정 구조
- 3일 프로젝트 범위 내 구현 가능

---

# 2. 전체 시스템 구성

Client (Browser)
│
│ HTTP (SSR + REST API)
│ WebSocket
▼
Flask Application
│
├── REST API Layer
├── WebSocket Layer (Flask-SocketIO)
├── Auth / Session Middleware
└── Business Logic
│
▼
MongoDB


---

# 3. 기술 스택

- Backend: Flask
- WebSocket: Flask-SocketIO
- Async Engine: eventlet
- Template Engine: Jinja2 (SSR)
- Database: MongoDB
- 배포: 단일 EC2 인스턴스

---

# 4. 계층 구조

## 4.1 Presentation Layer

- Jinja 기반 SSR 페이지
- 보드 진입 시 SSR로 초기 데이터 렌더링
- 이후 WebSocket으로 실시간 반영

익명 사용자:
- SSR 조회만 가능
- WebSocket 연결 대상 아님

로그인 사용자:
- SSR + WebSocket 연결

---

## 4.2 Application Layer

### 4.2.1 인증/세션 관리

- 로그인 성공 시 세션 생성
- 모든 쓰기 요청은 세션 검증 필수
- public_id 접근 시 DB 검증 수행

---

### 4.2.2 REST API

모든 데이터 변경은 반드시 HTTP로 수행한다.

| Method | 목적 |
|--------|------|
| POST | 생성 |
| PATCH | 수정/이동 |
| DELETE | 삭제 |

WebSocket은 DB 변경을 수행하지 않는다.

---

### 4.2.3 WebSocket Layer

역할:

- 변경 이벤트 broadcast
- 보드 단위 room 분리

접속 시:

```python
join_room(f"board_{public_id}")
```

broadcast는 해당 room으로만 수행한다.

이벤트 종류:
- note_created
- note_updated
- note_deleted
- board_invalidated

## 4.3 Persistence Layer (MongoDB)

### 4.3.1 users 컬렉션
```
{
  _id: UUID,
  username: string,
  password_hash: string,
  created_at: datetime
}
```

### 4.3.2 boards 컬렉션
```
{
  _id: ObjectId,
  owner_user_id: UUID,
  public_id: UUID,
  title: string,
  next_z_index: int,
  note_count: int,
  created_at: datetime,
  updated_at: datetime
}
```

title:
- 보드 제목. 선택적, 기본값 "" 또는 null.

next_z_index:
- z_index 원자적 증가용 카운터

note_count:
- 보드당 포스트잇 개수. 300개 제한 판정용. 생성 시 조건부 $inc, 삭제 시 $inc -1. countDocuments 대신 사용하여 부하 감소.
- 성능을 위한 근사값. insert 실패/삭제 실패/재시도로 드리프트 가능. 보정은 best-effort (예: insert 실패 시 $inc -1, 또는 주기적 countDocuments 보정).

### 4.3.3 sticky_notes 컬렉션
```
{
  _id: ObjectId,
  board_id: ObjectId,
  owner_user_id: UUID,
  text: string,
  image_key: string,
  x: int,
  y: int,
  z_index: int,
  version: int,
  created_at: datetime,
  updated_at: datetime
}
```

version:
- 낙관적 락 용도

### 4.3.4 snapshots 컬렉션
```
{
  _id: ObjectId,
  board_owner_id: UUID,
  image_key: string,
  is_public: boolean,
  created_at: datetime
}
```
---

# 5. 주요 설계 정책

## 5.1 접근 제어
- public_id를 아는 사용자는 보드 조회 가능
- 로그인 사용자는 public_id를 알고 있는 보드에 한해 쓰기 가능
- 보드 생성자는 해당 보드의 모든 포스트잇 CRUD 가능

## 5.2 public_id 변경 정책
public_id 변경 시:
1. DB의 public_id 업데이트
2. 기존 room에 board_invalidated 이벤트 broadcast
3. 클라이언트:
	- WebSocket 종료
	- 메인 페이지로 redirect
4. 이후 도착 요청은 최신 public_id 검증
5. 불일치 시 404 반환 (410 사용 안 함, public_id 조회 구조상 구분 불가)

## 5.3 낙관적 락 정책
- PATCH 요청 시 version 포함
- DB에서 version 일치 여부 확인
- 불일치 시 409 반환
- 성공 시 version +1 증가
- DB 성공 이후에만 WebSocket broadcast

WebSocket은 정합성을 보장하지 않는다.

## 5.4 z_index 정책
- 보드 단위 next_z_index 카운터 사용
- 포스트잇 생성/수정/이동 성공 시:
```
findOneAndUpdate(
  { board_id },
  { $inc: { next_z_index: 1 } }
)
```

- 반환된 값을 z_index로 사용
- 클릭 시 일시적 최상단 효과는 DB 반영하지 않음

## 5.5 300개 제한 정책
- boards.note_count로 판정. countDocuments 대신 사용(부하 감소)
- 생성 시 findOneAndUpdate로 note_count < 300 조건부 $inc 후 insert
- 정상 상태 ≤ 300. 동시 생성으로 일시 초과(301, 302) 가능
- 이후 생성 요청은 note_count >= 300이므로 실패
- 삭제 시 note_count $inc -1. 삭제 후 다시 생성 가능
- note_count 드리프트: best-effort 보정

## 5.6 삭제 정책
- 보드·포스트잇은 물리 삭제(hard delete). soft delete 미사용.
- 보드 삭제 시: sticky_notes.deleteMany({ board_id }) → boards.deleteOne({ _id }). boards 문서 삭제 시 note_count는 함께 제거되므로 별도 정리 불필요.

---

# 6. 요청 처리 흐름
## 6.1 포스트잇 수정
1. Client → PATCH (version 포함)
2. Server:
	- public_id 검증
	- version 검증
	- DB update
3. 성공 시 broadcast

## 6.2 public_id 변경
1. Owner 요청
2. DB 업데이트
3. board_invalidated broadcast
4. 이후 모든 요청 검증

---

# 7. 실시간 동기화 구조
- WebSocket 사용
- 보드 단위 room 분리
- 변경된 노트만 전송
- drag 중간 저장 금지
- drag 종료 시 1회 PATCH

최대 100명 동시 접속 가정.

---

# 8. 확장성 한계

현재 설계는:
- 단일 서버
- 단일 프로세스
- ≤ 100명 동시 접속

수평 확장은 고려하지 않음.

---

# 9. 보안 설계 원칙
- 모든 쓰기 요청은 세션 검증
- public_id 항상 DB 검증
- 클라이언트 입력 신뢰 금지
- WebSocket 이벤트는 DB 성공 이후만 발생

