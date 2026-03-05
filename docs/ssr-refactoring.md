# SSR 리팩토링 문서

> Issue: [#72 SSR 적용 리팩토링](https://github.com/hojun-lee99/jungle-mini-project-board/issues/72)

이 문서는 `publicList`(공개된 보드 기록)와 `snapshot`(내 보드 기록) 페이지에 SSR(Server-Side Rendering)을 적용한 리팩토링 과정을 설명합니다.

---

## 1. 개요

### 1.1 배경

기존에는 두 페이지 모두 **CSR(Client-Side Rendering)** 방식으로 동작했습니다.

- 서버: 빈 HTML shell만 반환
- 클라이언트: 페이지 로드 후 `GET /api/snapshots/public` 또는 `GET /api/snapshots/mine` 호출 → 응답 JSON으로 DOM 생성

### 1.2 SSR 전환 목적

- **초기 렌더링 속도**: HTML에 데이터가 포함되어 한 번의 요청으로 콘텐츠 표시
- **SEO**: 공개 목록(publicList) 검색 노출 개선
- **일관된 구조**: Jinja2 템플릿 기반으로 서버·클라이언트 역할 명확화

### 1.3 적용 대상

| 페이지 | 경로 | SSR 적용 여부 |
|--------|------|---------------|
| 공개된 보드 기록 | `/publicList` | ✅ 적용 |
| 내 보드 기록 | `/snapshot` | ✅ 적용 |
| 내 보드 목록 | `/main` | ❌ 미적용 |
| 칠판 | `/boards/<public_id>` | ❌ 미적용 |
| 로그인 | `/` | 이미 정적 폼, SSR 해당 없음 |

---

## 2. 리팩토링 패턴

### 2.1 공통 구조

```
[데이터 조회 헬퍼 함수]  ← routes/snapshots.py
        ↓
[페이지 라우트]          ← app.py
        ↓
[템플릿에 데이터 전달]   ← Jinja2 템플릿
        ↓
[초기 HTML 완성]        ← 클라이언트는 상호작용만 담당
```

### 2.2 핵심 원칙

1. **API·SSR 로직 공유**: 기존 API 엔드포인트와 동일한 조회 로직을 헬퍼 함수로 추출
2. **템플릿 변수 활용**: Jinja2 `{% for %}`로 초기 HTML 렌더
3. **상호작용 유지**: 이미지 확대, 공개 토글, 삭제 등은 기존 JS 이벤트 위임 유지

---

## 3. publicList (공개된 보드 기록)

### 3.1 Before (CSR)

```
서버: render_template('publicList.html')  → 빈 <ul id="card-list">
클라이언트: $(document).ready → showPublicSnapshots()
         → GET /api/snapshots/public
         → makePublicCard() 로 <li> 동적 생성
```

### 3.2 After (SSR)

#### 3.2.1 데이터 조회 헬퍼 (`routes/snapshots.py`)

```python
def get_public_snapshots(page=1, limit=20):
    """
    공개된 스냅샷 목록 조회. (list_public API·publicList SSR 공용)
    Returns: (items: list[dict], total: int)
    """
    db = getattr(current_app, "db", None)
    if db is None:
        return [], 0

    # ... DB 조회 및 serialize ...
    # 반환 필드: id, title, image_url, owner_username, created_at, label
    return [_serialize(d) for d in items], total
```

- `list_public` API 라우트가 이 헬퍼를 호출해 JSON 응답
- SSR 라우트도 동일 헬퍼를 호출해 템플릿에 전달

#### 3.2.2 페이지 라우트 (`app.py`)

```python
@app.route('/publicList')
def publicList():
    """공개된 보드 기록 페이지 (SSR)."""
    snapshots, _ = get_public_snapshots(page=1, limit=100)
    return render_template('publicList.html', snapshots=snapshots)
```

#### 3.2.3 템플릿 (`templates/publicList.html`)

```html
<ul class="board-grid" id="card-list">
    {% for s in snapshots|default([]) %}
    <li class="board-card" data-snapshot-id="{{ s.id }}">
        <div class="board-thumb board-thumb-clickable" data-image-url="{{ s.image_url }}">
            <img src="{{ s.image_url }}" alt="">
        </div>
        <div class="board-footer"><div class="board-name">{{ s.label }}</div></div>
    </li>
    {% endfor %}
</ul>
{% if not snapshots %}
<p class="public-empty" id="public-empty">공개된 보드 기록이 없습니다.</p>
{% endif %}
```

#### 3.2.4 제거된 CSR 로직

- `showPublicSnapshots()`: AJAX로 목록 로드
- `makePublicCard()`: 동적 카드 생성

#### 3.2.5 유지된 클라이언트 로직

- 이미지 클릭 → lightbox 확대 보기
- 사이드바 토글, 로그아웃, 네비게이션

---

## 4. snapshot (내 보드 기록)

### 4.1 Before (CSR)

```
서버: render_template('snapshot.html')  → 빈 <ul id="card-list">
클라이언트: $(document).ready → showSnapshots()
         → GET /api/snapshots/mine (JWT 필요)
         → makeSnapshotCard() 로 <li> 동적 생성
```

### 4.2 After (SSR)

#### 4.2.1 데이터 조회 헬퍼 (`routes/snapshots.py`)

```python
def get_mine_snapshots(user_id, page=1, limit=20):
    """
    내 스냅샷 목록 조회. (list_mine API·snapshot SSR 공용)
    Returns: (items: list[dict], total: int)
    """
    if not user_id:
        return [], 0
    # ... DB 조회 및 serialize ...
    # 반환 필드: id, title, image_url, is_public, created_at
    return [_serialize(d) for d in items], total
```

#### 4.2.2 페이지 라우트 (`app.py`)

```python
@app.route('/snapshot')
def snapshot():
    """내 보드 기록(스냅샷) 페이지 (SSR)."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        pass
    user_id = get_jwt_identity()
    if not user_id:
        return redirect('/')  # 비로그인 시 로그인 페이지로
    snapshots, _ = get_mine_snapshots(user_id=user_id, page=1, limit=100)
    return render_template('snapshot.html', snapshots=snapshots)
```

- **인증 필수**: 비로그인 시 `/`로 리다이렉트
- 로그인 사용자만 `get_mine_snapshots` 호출

#### 4.2.3 템플릿 (`templates/snapshot.html`)

```html
<ul class="board-grid" id="card-list">
    {% for s in snapshots|default([]) %}
    <li class="board-card" data-snapshot-id="{{ s.id }}">
        <div class="board-thumb board-thumb-clickable" data-image-url="{{ s.image_url }}">
            <img src="{{ s.image_url }}" alt="">
        </div>
        <div class="board-footer">
            <div class="board-name">{{ s.title or "제목 없음" }}</div>
            <div class="board-footer-actions">
                <div class="board-public">
                    <span>공개여부</span>
                    <input type="checkbox" class="public-toggle" data-id="{{ s.id }}" {% if s.is_public %}checked{% endif %}>
                </div>
                <button type="button" class="board-delete-btn" data-snapshot-id="{{ s.id }}" title="삭제">삭제</button>
            </div>
        </div>
    </li>
    {% endfor %}
</ul>
{% if not snapshots %}
<p class="snapshot-empty" id="snapshot-empty">보드 기록이 없습니다.</p>
{% endif %}
```

#### 4.2.4 제거된 CSR 로직

- `showSnapshots()`: AJAX로 목록 로드
- `makeSnapshotCard()`: 동적 카드 생성

#### 4.2.5 유지된 클라이언트 로직

- 공개 토글: `.public-toggle` change → `PATCH /api/snapshots/{id}`
- 삭제: `.board-delete-btn` click → `DELETE /api/snapshots/{id}`
- 이미지 lightbox, 사이드바, 로그아웃

---

## 5. 수정된 파일 요약

| 파일 | 변경 내용 |
|------|----------|
| `routes/snapshots.py` | `get_public_snapshots()`, `get_mine_snapshots()` 헬퍼 추가, API 라우트가 해당 헬퍼 사용 |
| `app.py` | `publicList()`, `snapshot()`에서 헬퍼 호출 후 템플릿에 `snapshots` 전달 |
| `templates/publicList.html` | Jinja2 `{% for %}`로 카드 렌더, CSR용 `showPublicSnapshots`/`makePublicCard` 제거 |
| `templates/snapshot.html` | Jinja2 `{% for %}`로 카드 렌더, CSR용 `showSnapshots`/`makeSnapshotCard` 제거 |

---

## 6. SSR 미적용 페이지와 사유

### 6.1 main (내 보드 목록)

- 로그인 필수 → SEO 이득 없음
- 개인화 데이터, 실시간 변경 빈번 → CSR이 적합

### 6.2 board (칠판)

- WebSocket 실시간 협업, 포스트잇 CRUD 등 클라이언트 상호작용 중심
- SSR 적용 시 Hydration 복잡도 증가
- 초기 HTML이 곧바로 WebSocket 동기화로 갱신될 수 있어 SSR 효과 제한적

### 6.3 login

- 정적 폼만 있어 이미 서버 렌더링
- 폼 제출은 클라이언트 → API 호출이 자연스러운 흐름
- CSR→SSR 전환이 필요한 구조가 아님

---

## 7. 참고

- API 엔드포인트(`GET /api/snapshots/public`, `GET /api/snapshots/mine`)는 그대로 유지되며, 다른 클라이언트(SPA, 모바일 앱 등)에서 재사용 가능
- 헬퍼 함수는 Flask `current_app` 컨텍스트 내에서 호출해야 함
- 빈 목록 시 `snapshots|default([])`, `{% if not snapshots %}`로 안전하게 처리
