$(document).ready(function () {
  const $container = $('#board-container');
  const publicId = $container.data('public-id');
  if (!publicId) {
    console.error('public_id가 없습니다.');
    return;
  }

  let board = null;
  let notes = [];

  function loadBoard() {
    fetch(`/api/boards/${publicId}`, { credentials: 'include' })
      .then((res) => {
        if (!res.ok) {
          if (res.status === 404) {
            throw new Error('유효하지 않은 보드 링크입니다.');
          }
          throw new Error('보드를 불러올 수 없습니다.');
        }
        return res.json();
      })
      .then((data) => {
        board = data.board;
        notes = data.notes || [];
        renderBoard();
        renderNotes();
      })
      .catch((err) => {
        alert(err.message || '보드 로드 실패');
      });
  }

  function renderBoard() {
    $('#board-title').text(board?.title || '보드 제목');
  }

  function renderNotes() {
    $container.find('.note').remove();
    notes.forEach((note) => {
      const $el = $('<div>')
        .addClass('note')
        .css({
          left: note.x + 'px',
          top: note.y + 'px',
          zIndex: note.z_index,
        })
        .attr('data-note-id', note.id)
        .attr('data-version', note.version);

      if (note.image_url) {
        $el.append($('<img>').attr('src', note.image_url).css({ maxWidth: '100%', display: 'block', marginBottom: 4 }));
      }
      $el.append($('<div>').addClass('note-text').text(note.text || ''));

      $container.append($el);
    });
  }

  function createNote(x, y, text) {
    fetch(`/api/boards/${publicId}/notes`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text || '새 메모', x, y }),
    })
      .then(async (res) => {
        if (res.status === 401) {
          alert('로그인이 필요합니다. 새 포스트잇을 추가하려면 로그인해 주세요.');
          return null;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data?.error?.message || '포스트잇 생성에 실패했습니다.');
        }
        return res.json();
      })
      .then((note) => {
        if (note) {
          notes.push(note);
          renderNotes();
        }
      })
      .catch((err) => {
        alert(err.message || '포스트잇 생성 실패');
      });
  }

  loadBoard();

  // 공유 버튼
  $('#btn-share').on('click', function () {
    const url = window.location.href;
    navigator.clipboard
      .writeText(url)
      .then(() => alert('현재 보드 링크가 클립보드에 복사되었습니다.'))
      .catch(() => alert('복사에 실패했습니다. 링크: ' + url));
  });

  // 이미지 추가 버튼
  $('#btn-add-image').on('click', function () {
    console.log('이미지 업로드 모달을 엽니다.');
  });

  // 햄버거 메뉴 → 우측 윙바 오버레이 열기
  function openWingbar() {
    $('#wingbar-backdrop, #wingbar').addClass('is-open').attr('aria-hidden', 'false');
  }
  function closeWingbar() {
    $('#wingbar-backdrop, #wingbar').removeClass('is-open').attr('aria-hidden', 'true');
  }

  $('#btn-menu').on('click', openWingbar);
  $('#btn-close-wingbar').on('click', closeWingbar);
  $('#wingbar-backdrop').on('click', closeWingbar);

  // 로그아웃
  $('#btn-logout').on('click', function () {
    fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
      .then(() => {
        closeWingbar();
        window.location.href = '/';
      })
      .catch(() => alert('로그아웃에 실패했습니다.'));
  });

  // 보드 빈 공간 더블클릭 → 새 포스트잇 생성
  $container.on('dblclick', function (e) {
    if ($(e.target).closest('.note').length) return;
    const x = e.offsetX;
    const y = e.offsetY;
    const text = prompt('포스트잇 내용을 입력하세요:', '새 메모') || '새 메모';
    createNote(x, y, text);
  });
});
