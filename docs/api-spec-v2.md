# API 명세서 (v2)
## Jungle Whiteboard

---

## 1. 개요

본 문서는 요구사항 정의서(v2) 및 시스템 아키텍처(v2)를 기반으로 Jungle Whiteboard의 REST API 및 WebSocket 이벤트 명세를 정의한다.

### 1.1 기본 규칙

- **Base URL**: `{host}/api`
- **인증**: 세션 기반 (로그인 사용자만 쓰기 작업 가능)
- **Content-Type**: `application/json` (이미지 업로드 시 `multipart/form-data`)
- **데이터 변경**: 모든 생성/수정/삭제는 HTTP로 수행 (WebSocket은 broadcast만 수행)
- **z_index**: 서버 전용 필드. 클라이언트는 요청 시 `z_index`를 포함해도 안 되며, 서버가 자동 부여한다. 응답에서만 수신한다.  
  z_index 갱신 시점: **POST(생성)** 성공 시, **PATCH(수정/이동)** 성공 시. PATCH는 내용 수정(text, image_key)이든 좌표 이동(x, y)이든 **성공하면 무조건** 해당 포스트잇을 최상단으로 올린다. (요구사항: "수정 저장 또는 이동 저장(PATCH 성공) 시 최상단 반영")

### 1.2 공통 응답 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 201 | 생성 성공 |
| 204 | 삭제 성공 (No Content) |
| 400 | 잘못된 요청 |
| 401 | 비인증 (로그인 필요) |
| 403 | 권한 없음 / 할당량 초과 |
| 404 | 리소스 없음. `BOARD_NOT_FOUND` / `NOTE_NOT_FOUND` / `SNAPSHOT_NOT_FOUND` |
| 409 | Conflict (버전 충돌 등) |
| 422 | 유효성 검증 실패 |
| 500 | 서버 오류 |

### 1.3 보드당 포스트잇 300개 제한 정책

- 보드당 최대 300개의 포스트잇을 허용한다.
- **구현 권장**: boards 컬렉션에 `note_count` 필드를 두고, 생성 시 `findOneAndUpdate`로 조건부 증가를 사용한다. `countDocuments` 매 요청 호출은 부하가 크며, 300 초과 상태에서 계속 403을 반환할 때도 비용이 든다.
- **판정**: `note_count < 300` 조건으로 `findOneAndUpdate` 시도. 조건 불만족 시 insert 없이 403 반환. 성공 시 note 삽입. 동시 생성으로 301, 302까지 허용되며, 초과 시 `note_count`가 300 이상이므로 이후 생성은 실패한다. 삭제 시 `note_count` 감소.

**note_count 드리프트**: `note_count`는 성능을 위한 근사값이며, insert 실패·삭제 실패·재시도 등으로 드리프트가 발생할 수 있다. 드리프트 방지/보정은 best-effort로 처리한다. (예: insert 실패 시 `$inc: -1` 보정 시도. 또는 보드 조회 시/주기적으로 countDocuments로 보정하는 옵션.)

**제한 초과 시 응답** `403 Forbidden`
```json
{
  "error": {
    "code": "NOTE_LIMIT_EXCEEDED",
    "message": "보드당 포스트잇 최대 300개 제한을 초과했습니다.",
    "details": { "current_count": 300 }
  }
}
```

---

## 2. 인증 API

### 2.1 회원가입

**POST** `/api/auth/register`

| 구분 | 내용 |
|------|------|
| 인증 | 불필요 |
| 설명 | 신규 사용자 회원가입 |

**Request Body**
```json
{
  "username": "string",  // 작성자 표기용 이름
  "password": "string"
}
```

**성공 응답** `201 Created`
```json
{
  "user_id": "uuid",
  "username": "string"
}
```

**에러**
- `400`: username 중복
- `422`: 유효성 검증 실패

---

### 2.2 로그인

**POST** `/api/auth/login`

| 구분 | 내용 |
|------|------|
| 인증 | 불필요 |
| 설명 | 로그인 후 세션 생성 |

**Request Body**
```json
{
  "username": "string",
  "password": "string"
}
```

**성공 응답** `200 OK`
```json
{
  "user_id": "uuid",
  "username": "string"
}
```

**에러**
- `401`: 아이디/비밀번호 불일치

---

### 2.3 로그아웃

**POST** `/api/auth/logout`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 (로그인 사용자) |
| 설명 | 세션 무효화 |

**성공 응답** `204 No Content`

---

## 3. 보드 API

### 3.1 보드 생성

**POST** `/api/boards`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 새 보드 생성 |

**Request Body**
```json
{
  "title": "string"  // 선택적, 보드 제목
}
```

**성공 응답** `201 Created`
```json
{
  "id": "objectid",
  "public_id": "uuid",
  "owner_user_id": "uuid",
  "title": "string",
  "created_at": "datetime"
}
```

---

### 3.2 내 보드 목록 조회

**GET** `/api/boards`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 로그인 사용자가 생성한 살아있는(삭제되지 않은) 보드 목록 |

**Query Parameters**
- `page` (선택): 페이지 번호
- `limit` (선택): 페이지당 개수 (기본 20)

**성공 응답** `200 OK`
```json
{
  "boards": [
    {
      "id": "objectid",
      "public_id": "uuid",
      "owner_user_id": "uuid",
      "title": "string",
      "created_at": "datetime"
    }
  ],
  "total": 0
}
```

---

### 3.3 보드 조회 (SSR/API)

**GET** `/api/boards/{public_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 불필요 (public_id를 아는 누구나 조회 가능) |
| 설명 | 보드 및 포스트잇 목록 조회 |

**Path Parameters**
- `public_id`: 보드의 공개 식별자 (UUID)

**성공 응답** `200 OK`
```json
{
  "board": {
    "id": "objectid",
    "public_id": "uuid",
    "owner_user_id": "uuid",
    "title": "string"
  },
  "notes": [
    {
      "id": "objectid",
      "owner_user_id": "uuid",
      "text": "string",
      "image_url": "string",
      "x": 0,
      "y": 0,
      "z_index": 0,
      "version": 0,
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ]
}
```

**에러**
- `404`: `BOARD_NOT_FOUND` — 유효하지 않은 보드 링크입니다. (`message`는 사용자 친화적 문구 사용. 내부적으로 "없음/삭제됨/public_id 변경" 구분 불가)

---

### 3.4 보드 public_id 변경

**PATCH** `/api/boards/{public_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 (보드 생성자만) |
| 설명 | 보드의 public_id를 새 UUID로 변경. 기존 public_id로 접속 중인 모든 클라이언트에 board_invalidated broadcast |

**Request Body**
```json
{
  "public_id": "uuid"  // 새 public_id
}
```

**성공 응답** `200 OK`
```json
{
  "public_id": "uuid"
}
```

**에러**
- `401`: 비인증
- `403`: 보드 생성자 아님
- `404`: `BOARD_NOT_FOUND` — 유효하지 않은 보드 링크

---

### 3.5 보드 삭제

**DELETE** `/api/boards/{public_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 (보드 생성자만) |
| 설명 | 보드 삭제. 최종 스냅샷을 이미지로 저장 후 보드 소유자에게 귀속 |

**삭제 방식**: 보드·포스트잇은 **물리 삭제(hard delete)**. soft delete 미사용.

**처리 순서**
1. 스냅샷 이미지 파일 생성 (외부 스토리지/로컬 디스크)
2. snapshots 컬렉션에 레코드 저장 (소유자 귀속)
3. `sticky_notes.deleteMany({ board_id })` → `boards.deleteOne({ _id })`. notes를 먼저 삭제한 뒤 boards 문서 삭제. (boards 삭제 시 note_count는 문서와 함께 사라지므로 별도 정리 불필요)
4. 해당 보드 room에 `board_invalidated` broadcast (7.2 참고)

**DB 관점**: 보드 삭제(3단계)는 스냅샷 레코드(2단계) 저장까지 성공한 경우에만 진행한다. 2단계 실패 시 3단계를 수행하지 않고 `500`/`503` 반환.

**파일 스토리지 관점**: 이미지 파일 생성/삭제는 best-effort이다. 스토리지가 DB 밖에 있으므로 DB 트랜잭션으로 원자성을 보장할 수 없다. 실패 시 orphan 파일이 남을 수 있으며, 추후 정리 대상이다.

**성공 응답** `204 No Content`

**에러**
- `401`: 비인증
- `403`: 보드 생성자 아님
- `404`: `BOARD_NOT_FOUND` — 유효하지 않은 보드 링크
- `500` / `503`: 스냅샷 레코드 저장 실패 (보드 삭제 미진행)

---

## 4. 포스트잇 API

### 4.1 포스트잇 생성

**POST** `/api/boards/{public_id}/notes`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 (로그인 사용자) |
| 설명 | 포스트잇 생성. 보드당 최대 300개 제한 |

**Request Body**
```json
{
  "text": "string",      // 최대 500자
  "image_key": "string", // 선택, 업로드된 이미지의 key
  "x": 0,
  "y": 0
}
```
※ `z_index`는 포함하지 않는다. 서버가 자동 부여한다.

**성공 응답** `201 Created`
```json
{
  "id": "objectid",
  "owner_user_id": "uuid",
  "text": "string",
  "image_url": "string",
  "x": 0,
  "y": 0,
  "z_index": 0,
  "version": 0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**에러**
- `401`: 비인증
- `403`: `NOTE_LIMIT_EXCEEDED` — 보드당 300개 제한 초과 (1.3 참고)
- `404`: `BOARD_NOT_FOUND` — 유효하지 않은 보드 링크
- `422`: text 500자 초과, 유효성 검증 실패

---

### 4.2 포스트잇 수정/이동

**PATCH** `/api/boards/{public_id}/notes/{note_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 포스트잇 내용 수정 또는 위치 이동. 보드 생성자 또는 포스트잇 작성자만 가능. 낙관적 락(version) 적용 |

**Request Body**
```json
{
  "version": 0,          // 필수, 클라이언트가 보유한 버전
  "text": "string",      // 선택, 수정 시
  "image_key": "string|null", // 선택. null이면 기존 이미지 삭제, 생략 시 유지
  "x": 0,                // 선택, 이동 시
  "y": 0                 // 선택, 이동 시
}
```
※ `z_index`는 포함하지 않는다. PATCH 성공 시(내용 수정·이동 모두) 서버가 최상단으로 자동 부여한다.

**image_key 의미**
| 값 | 동작 |
|----|------|
| 생략(omitted) | 기존 이미지 유지 |
| `null` | 기존 이미지 삭제 (이미지가 있던 경우 삭제 시도) |
| `"string"` | 새 이미지 key로 교체 |

**변경 없음(no-op)**: `version`만 있고 수정 가능 필드(text, image_key, x, y)를 하나도 포함하지 않으면 `400 Bad Request`를 반환한다. `error.code`: `NO_CHANGES`.  
변경 필드를 포함했으나 기존값과 동일한 경우는 검증하지 않으며, `200 OK`로 처리한다(또는 version 증가 없이 200 반환). 기존값 비교는 추가 read 비용과 version 경합(409 vs 400) 애매함을 유발하므로 강제하지 않는다.

**성공 응답** `200 OK`
```json
{
  "id": "objectid",
  "owner_user_id": "uuid",
  "text": "string",
  "image_url": "string",
  "x": 0,
  "y": 0,
  "z_index": 0,
  "version": 1,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**에러**
- `400`: `NO_CHANGES` — version만 있고 변경 필드 없음
- `401`: 비인증
- `403`: 수정 권한 없음 (작성자 또는 보드 생성자 아님)
- `404`: `BOARD_NOT_FOUND` (보드 검증 실패) 또는 `NOTE_NOT_FOUND` (note가 해당 보드에 없음)
- `409`: Conflict (version 불일치)

---

### 4.3 포스트잇 삭제

**DELETE** `/api/boards/{public_id}/notes/{note_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 포스트잇 삭제. 보드 생성자 또는 포스트잇 작성자만 가능. 이미지 파일도 삭제 시도 |

**성공 응답** `204 No Content`

**에러**
- `401`: 비인증
- `403`: 삭제 권한 없음
- `404`: `BOARD_NOT_FOUND` (보드 검증 실패) 또는 `NOTE_NOT_FOUND` (note가 해당 보드에 없음)

---

## 5. 이미지 업로드 API

### 5.1 이미지 업로드 (포스트잇용)

**POST** `/api/boards/{public_id}/images`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 포스트잇에 첨부할 이미지 업로드 |

**Content-Type** `multipart/form-data`

**Request Body (Form)**
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| file | File | O | 이미지 파일 (jpg, jpeg, png, gif, 최대 3MB) |

**성공 응답** `201 Created`
```json
{
  "image_key": "string",
  "url": "string"
}
```

**에러**
- `400`: 허용 확장자 아님, 3MB 초과, 이미지 아님
- `401`: 비인증
- `404`: `BOARD_NOT_FOUND` — 유효하지 않은 보드 링크

---

## 6. 스냅샷 API

### 6.1 내 스냅샷 목록

**GET** `/api/snapshots/mine`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 |
| 설명 | 나에게 귀속된 보드 스냅샷 목록 |

**Query Parameters**
- `page` (선택): 페이지 번호
- `limit` (선택): 페이지당 개수 (기본 20)

**성공 응답** `200 OK`
```json
{
  "snapshots": [
    {
      "id": "objectid",
      "image_url": "string",
      "is_public": false,
      "created_at": "datetime"
    }
  ],
  "total": 0
}
```

---

### 6.2 스냅샷 공개 여부 토글

**PATCH** `/api/snapshots/{snapshot_id}`

| 구분 | 내용 |
|------|------|
| 인증 | 필수 (스냅샷 소유자만) |
| 설명 | 공개/비공개 토글 |

**Request Body**
```json
{
  "is_public": true
}
```

**성공 응답** `200 OK`
```json
{
  "id": "objectid",
  "is_public": true
}
```

**에러**
- `401`: 비인증
- `403`: 소유자 아님
- `404`: `SNAPSHOT_NOT_FOUND`

---

### 6.3 공개 스냅샷 게시판

**GET** `/api/snapshots/public`

| 구분 | 내용 |
|------|------|
| 인증 | 불필요 |
| 설명 | 모든 사용자가 공개 전환한 스냅샷 목록 |

**Query Parameters**
- `page` (선택): 페이지 번호
- `limit` (선택): 페이지당 개수 (기본 20)

**성공 응답** `200 OK`
```json
{
  "snapshots": [
    {
      "id": "objectid",
      "image_url": "string",
      "owner_username": "string",
      "created_at": "datetime"
    }
  ],
  "total": 0
}
```

---

## 7. WebSocket 이벤트

### 7.1 연결 및 인증

- **엔드포인트**: `/socket.io`
- **인증**: HTTP 세션과 동일한 세션 쿠키 사용. WebSocket handshake 시 브라우저가 same-origin 요청으로 쿠키를 자동 전송한다.
- **세션 공유**: Flask-SocketIO는 HTTP 애플리케이션과 세션을 공유하므로, 로그인된 사용자의 쿠키로 handshake 시 인증이 가능하다.
- **Room 가입**: 보드 페이지 진입 시 서버가 `join_room("board_{public_id}")` 처리
- **대상**: 로그인 사용자만 WebSocket 연결 가능. 익명 사용자는 SSR 조회만 가능

**Handshake 인증 실패 시**
- 서버는 WebSocket 연결을 수락하지 않고 거부한다.
- 클라이언트는 `connect_error`(또는 해당 라이브러리 equivalent)로 수신하며, `authentication_required`를 에러 payload로 전달한다. close reason은 구현 종속적이므로 명세에서 정의하지 않는다.
- 클라이언트는 재연결 시 로그인 상태를 확인하고, 미로그인 시 연결 시도하지 않는다.

---

### 7.2 서버 → 클라이언트 이벤트

| 이벤트명 | payload | 설명 |
|----------|---------|------|
| `note_created` | `{ note: {...} }` | 새 포스트잇 생성 완료 시 broadcast |
| `note_updated` | `{ note: {...} }` | 포스트잇 수정/이동 완료 시 broadcast |
| `note_deleted` | `{ note_id: "objectid" }` | 포스트잇 삭제 완료 시 broadcast |
| `board_invalidated` | `{}` | public_id 변경 또는 **보드 삭제** 시, 해당 room 전체에 broadcast. 클라이언트는 연결 해제 후 메인 페이지로 리다이렉트 |

**board_invalidated 발생 조건**
- public_id 변경: 기존 room에 broadcast 후 room 의미 소멸
- 보드 삭제: 스냅샷 저장 및 보드 삭제 완료 후, 해당 room에 broadcast. 이후 room은 더 이상 존재하지 않음

---

### 7.3 정책

- WebSocket은 DB 변경을 수행하지 않음. 모든 생성/수정/삭제는 HTTP로 처리
- broadcast는 DB 업데이트(또는 보드 삭제) 성공 이후에만 수행
- version 충돌(409) 시 broadcast 발생하지 않음
- `board_invalidated` 수신 시 클라이언트는 반드시 WebSocket 연결 해제 및 메인 페이지로 이동

---

## 8. 부록: 공통 에러 응답 형식

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

| code | 설명 |
|------|------|
| `VALIDATION_ERROR` | 유효성 검증 실패 |
| `UNAUTHORIZED` | 비인증 |
| `FORBIDDEN` | 권한 없음 |
| `NOTE_LIMIT_EXCEEDED` | 보드당 포스트잇 300개 제한 초과 (HTTP 403) |
| `NO_CHANGES` | PATCH 요청에 변경할 필드 없음 (HTTP 400) |
| `BOARD_NOT_FOUND` | 보드 없음. 유효하지 않은 보드 링크 (HTTP 404) |
| `NOTE_NOT_FOUND` | 포스트잇 없음 또는 해당 보드에 속하지 않음 (HTTP 404) |
| `SNAPSHOT_NOT_FOUND` | 스냅샷 없음 (HTTP 404) |
| `CONFLICT` | 버전 충돌 등 |

---

## 9. 공통 처리 정책

### 9.1 public_id 검증 및 요청 처리 순서

보드 관련 모든 API(`/api/boards/{public_id}/*`)는 다음 순서로 처리한다:

1. **보드 조회 (최우선)**  
   `boards.findOne({ public_id: path_public_id })`로 보드를 조회한다. 경로의 `public_id`는 boards 컬렉션의 유일한 조회 키이다.  
   - **결과 없음** → 즉시 `404` 반환. 이후 단계로 진행하지 않는다.

2. 인증 검증 (쓰기 요청 시)

3. 권한 검증

4. 비즈니스 로직 (version 검증, DB 업데이트 등)

**note 수정/삭제 시 board_id 필수**: 포스트잇 PATCH/DELETE는 DB 쿼리 조건에 반드시 `board_id`를 포함해야 한다. 경로의 `public_id`로 조회한 보드의 `_id`를 사용한다. `note_id`만으로 조회·수정하면 다른 보드의 노트를 변경할 수 있는 버그가 발생한다.

예: `sticky_notes.updateOne({ _id: note_id, board_id: board._id, version: req.version }, {...})`

**404로 통일하는 이유**: public_id가 변경되면 이전 값은 DB에 남지 않는다. 따라서 `findOne({ public_id: old })` 결과가 없을 때 "한 번도 없었음"과 "있었으나 public_id 변경으로 무효화됨"을 구분할 수 없다. 410(Gone)을 반환하려면 deprecated public_id를 별도 저장해야 하며, 현재 설계 범위를 벗어난다. **모두 404로 통일**한다.

**동시성 시나리오**: A가 PATCH(note)를 `old_public_id`로 보냈다. 그 사이 B가 public_id를 변경하여 DB에는 `new_public_id`만 존재한다. A의 요청이 도착하면 `findOne({ public_id: old_public_id })` 결과가 없으므로 404가 반환된다.
