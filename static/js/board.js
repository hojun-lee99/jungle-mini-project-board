$(document).ready(function () {
  const $container = $('#board-container');
  const publicId = $container.data('public-id');
  if (!publicId) {
    console.error('public_id가 없습니다.');
    return;
  }

  let board = null;
  let notes = [];
  let currentUserId = null;
  let imageInsertMode = false;
  let pendingImagePosition = null;

  function loadBoard() {
    fetch(`/api/boards/${publicId}`, { credentials: 'include' })
      .then((res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error('유효하지 않은 보드 링크입니다.');
          throw new Error('보드를 불러올 수 없습니다.');
        }
        return res.json();
      })
      .then((data) => {
        board = data.board;
        notes = data.notes || [];
        currentUserId = data.current_user_id || null;
        renderBoard();
        renderNotes();
        renderWingbarMyNotes();
      })
      .catch((err) => alert(err.message || '보드 로드 실패'));
  }

  function renderWingbarMyNotes() {
    const $list = $('#wingbar-my-notes');
    const $empty = $('#wingbar-my-notes-empty');
    $list.empty();

    if (!currentUserId) {
      $empty.text('로그인하면 내가 쓴 메모를 볼 수 있습니다.').show();
      return;
    }

    const myNotes = notes.filter((n) => String(n.owner_user_id) === String(currentUserId));

    if (myNotes.length === 0) {
      $empty.text('쓴 메모가 없습니다.').show();
      $list.hide();
      return;
    }

    $empty.hide();
    $list.show();
    myNotes.forEach((note) => {
      const text = note.text || (note.image_url ? '[이미지]' : '(내용 없음)');
      const $li = $('<li>')
        .addClass('wingbar-note-item')
        .attr('title', text)
        .text(text.length > 30 ? text.slice(0, 30) + '…' : text);
      $list.append($li);
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
        $el.append(
          $('<img>')
            .attr('src', note.image_url)
            .css({ maxWidth: '100%', display: 'block', marginBottom: 4, borderRadius: 4 })
        );
      }
      $el.append($('<div>').addClass('note-text').text(note.text || ''));

      $container.append($el);
    });
  }

  function createNote(x, y, text, imageKey) {
    const body = { text: text || '', x, y };
    if (imageKey) body.image_key = imageKey;

    fetch(`/api/boards/${publicId}/notes`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(async (res) => {
        if (res.status === 401) {
          alert('로그인이 필요합니다.');
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
          renderWingbarMyNotes();
        }
      })
      .catch((err) => alert(err.message));
  }

  loadBoard();

  // 공유
  $('#btn-share').on('click', function () {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => alert('현재 보드 링크가 클립보드에 복사되었습니다.'))
      .catch(() => alert('복사에 실패했습니다.'));
  });

  // 이미지 추가 모드
  $('#btn-add-image').on('click', function (e) {
    e.stopPropagation();
    imageInsertMode = !imageInsertMode;
    $(this).toggleClass('image-mode-active', imageInsertMode);
    if (!imageInsertMode) closeImageModal();
  });

  // 윙바
  function openWingbar() {
    $('#wingbar-backdrop, #wingbar').addClass('is-open').attr('aria-hidden', 'false');
  }
  function closeWingbar() {
    $('#wingbar-backdrop, #wingbar').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $('#btn-menu').on('click', openWingbar);
  $('#btn-close-wingbar').on('click', closeWingbar);
  $('#wingbar-backdrop').on('click', closeWingbar);

  // 보드 더블클릭 → 포스트잇 생성
  $container.on('dblclick', function (e) {
    if ($(e.target).closest('.note').length) return;
    if (imageInsertMode) return;
    const x = e.offsetX;
    const y = e.offsetY;
    const text = prompt('포스트잇 내용을 입력하세요:', '새 메모') || '새 메모';
    createNote(x, y, text);
  });

  // 보드 클릭 (이미지 모드) → 이미지 삽입 UI
  $container.on('click', function (e) {
    if (!imageInsertMode) return;
    if ($(e.target).closest('.note').length) return;
    e.preventDefault();
    e.stopPropagation();
    pendingImagePosition = { x: e.offsetX, y: e.offsetY };
    openImageModal();
  });

  // 이미지 모달
  function openImageModal() {
    $('#image-modal').addClass('is-open').attr('aria-hidden', 'false');
    $('#image-file-input').val('');
  }
  function closeImageModal() {
    $('#image-modal').removeClass('is-open').attr('aria-hidden', 'true');
    pendingImagePosition = null;
  }

  $(document).on('click', '.image-modal-backdrop[data-close="true"]', closeImageModal);
  $('#image-modal-cancel').on('click', closeImageModal);

  $('#image-modal-confirm').on('click', function () {
    const input = document.getElementById('image-file-input');
    if (!input.files || !input.files[0]) {
      alert('이미지 파일을 선택해 주세요.');
      return;
    }
    if (!pendingImagePosition) {
      closeImageModal();
      return;
    }
    const { x, y } = pendingImagePosition;
    const formData = new FormData();
    formData.append('file', input.files[0]);

    fetch(`/api/boards/${publicId}/images`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    })
      .then(async (res) => {
        if (res.status === 401) {
          alert('로그인이 필요합니다.');
          return null;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data?.error?.message || '이미지 업로드에 실패했습니다.');
        }
        return res.json();
      })
      .then((data) => {
        if (data) {
          createNote(x, y, '', data.image_key);
          closeImageModal();
          imageInsertMode = false;
          $('#btn-add-image').removeClass('image-mode-active');
        }
      })
      .catch((err) => alert(err.message));
  });
});
