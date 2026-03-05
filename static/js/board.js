$(document).ready(function () {
  const $container = $('#board-container');
  const publicId = $container.data('public-id');
  if (!publicId) {
    console.error('public_id가 없습니다.');
    return;
  }
  $('#login-required-goto').attr('href', '/?next=' + encodeURIComponent('/boards/' + publicId));
  $('#btn-login').attr('href', '/?next=' + encodeURIComponent('/boards/' + publicId));

  let board = null;
  let notes = [];
  let currentUserId = null;
  let imageInsertMode = false;
  let pendingImagePosition = null;

  const socket = io('/', {
    withCredentials: true,
  });

  socket.on('connect', function () {
    console.log('웹소켓 서버에 연결되었습니다!');

    socket.emit('join_board', { public_id: publicId });
  });

  socket.on('connect_error', function (err) {
    console.error('웹소켓 연결 실패 (인증 오류 등):', err.message);
  });

  socket.on('disconnect', function () {
    console.log('웹소켓 연결이 끊어졌습니다.');
  });

  socket.on('note_moved', function (data) {
    if (dragging.noteId !== String(data.note_id)) {
      const $note = $container.find(`.note[data-note-id="${data.note_id}"]`);

      if ($note.length) {
        $note.animate(
          {
            left: data.x + 'px',
            top: data.y + 'px',
          },
          300,
        );

        const noteObj = notes.find(
          (n) => String(n.id) === String(data.note_id),
        );
        if (noteObj) {
          noteObj.x = data.x;
          noteObj.y = data.y;

          if (data.version !== undefined) {
            noteObj.version = data.version;
          }
        }
      }
    }
  });

  socket.on('note_created', function (data) {
    if (data && data.note) {
      const exists = notes.find((n) => String(n.id) === String(data.note.id));

      if (!exists) {
        notes.push(data.note);
        renderNotes();
      }
    }
  })

  socket.on('note_deleted', function (data) {
    if (data && data.note_id) {
      notes = notes.filter((n) => String(n.id) !== String(data.note_id))
      renderNotes();
    }
  })

  socket.on('note_updated', function (data) {
    if (data && data.note) {
      const idx = notes.findIndex((n) => String(n.id) === String(data.note.id));

      if (idx !== -1) {
        notes[idx] = data.note;
        renderNotes();
      }
    }
  })

  function loadBoard() {
    fetch(`/api/boards/${publicId}`, { credentials: 'include' })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (res.status === 404)
            throw new Error('유효하지 않은 보드 링크입니다.');
          throw new Error(data?.error?.message || '보드를 불러올 수 없습니다.');
        }
        return data;
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

    const myNotes = notes.filter(
      (n) => String(n.owner_user_id) === String(currentUserId),
    );

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
        .attr('data-note-id', note.id)
        .attr('title', text)
        .text(text.length > 30 ? text.slice(0, 30) + '…' : text);
      $list.append($li);
    });
  }

  function highlightNote(noteId) {
    $container.find('.note').removeClass('is-highlighted');
    $('#wingbar-my-notes .wingbar-note-item').removeClass('is-active');
    if (noteId) {
      $container
        .find('.note[data-note-id="' + noteId + '"]')
        .addClass('is-highlighted');
      $(
        '#wingbar-my-notes .wingbar-note-item[data-note-id="' + noteId + '"]',
      ).addClass('is-active');
    }
  }

  function renderBoard() {
    $('#board-title').text(board?.title || '보드 제목');
    if (!currentUserId) {
      $('#btn-login').show();
    } else {
      $('#btn-login').hide();
    }
    const isBoardOwner = !!(currentUserId && board && String(board.owner_user_id) === String(currentUserId));
    if (isBoardOwner) {
      $('#board-title').css('cursor', 'pointer');
      $('#wingbar-regenerate-link').show();
    } else {
      $('#board-title').css('cursor', 'default');
      $('#wingbar-regenerate-link').hide();
    }
  }

  function openBoardTitleModal() {
    $('#board-title-input').val(board?.title || '');
    $('#board-title-modal').addClass('is-open').attr('aria-hidden', 'false');
    setTimeout(() => $('#board-title-input').focus(), 100);
  }
  function closeBoardTitleModal() {
    $('#board-title-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $(document).on('click', '#board-title-modal .note-modal-backdrop[data-close="true"]', closeBoardTitleModal);
  $('#board-title-cancel').on('click', closeBoardTitleModal);
  $('#board-title-save').on('click', function () {
    const title = String($('#board-title-input').val() || '').trim();
    fetch(`/api/boards/${publicId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || '' }),
    })
      .then(async (res) => {
        if (res.status === 401) { showLoginRequiredModal(); return null; }
        if (res.status === 403) { alert('보드 생성자만 제목을 수정할 수 있습니다.'); return null; }
        if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d?.error?.message || '수정 실패'); }
        return res.json();
      })
      .then((data) => {
        if (data && data.title !== undefined) {
          board = board || {};
          board.title = data.title;
          $('#board-title').text(data.title || '보드 제목');
          closeBoardTitleModal();
          alert('보드 제목이 저장되었습니다.');
        }
      })
      .catch((err) => alert(err.message));
  });

  $(document).on('click', '#board-title', function () {
    const isBoardOwner = !!(currentUserId && board && String(board.owner_user_id) === String(currentUserId));
    if (isBoardOwner) openBoardTitleModal();
  });

  function openBoardTitleModal() {
    $('#board-title-input').val(board?.title || '');
    $('#board-title-modal').addClass('is-open').attr('aria-hidden', 'false');
    setTimeout(() => $('#board-title-input').focus(), 100);
  }
  function closeBoardTitleModal() {
    $('#board-title-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $(document).on(
    'click',
    '#board-title-modal .note-modal-backdrop[data-close="true"]',
    closeBoardTitleModal,
  );
  $('#board-title-cancel').on('click', closeBoardTitleModal);
  $('#board-title-save').on('click', function () {
    const title = String($('#board-title-input').val() || '').trim();
    fetch(`/api/boards/${publicId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || '' }),
    })
      .then(async (res) => {
        if (res.status === 401) {
          showLoginRequiredModal();
          return null;
        }
        if (res.status === 403) {
          alert('보드 생성자만 제목을 수정할 수 있습니다.');
          return null;
        }
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d?.error?.message || '수정 실패');
        }
        return res.json();
      })
      .then((data) => {
        if (data && data.title !== undefined) {
          board = board || {};
          board.title = data.title;
          $('#board-title').text(data.title || '보드 제목');
          closeBoardTitleModal();
          alert('보드 제목이 저장되었습니다.');
        }
      })
      .catch((err) => alert(err.message));
  });

  $(document).on('click', '#board-title', function () {
    const isBoardOwner = !!(
      currentUserId &&
      board &&
      String(board.owner_user_id) === String(currentUserId)
    );
    if (isBoardOwner) openBoardTitleModal();
  });

  function updateNotePosition(noteId, x, y, version) {
    const note = notes.find((n) => n.id === noteId);
    if (!note) return;

    const previousX = note.x;
    const previousY = note.y;

    note.x = x;
    note.y = y;

    fetch(`/api/boards/${publicId}/notes/${noteId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version: note.version,
        x: Math.round(x),
        y: Math.round(y),
      }),
    })
      .then(async (res) => {
        if (res.status === 401) {
          showLoginRequiredModal();
          note.x = previousX;
          note.y = previousY;
          renderNotes();
          return null;
        }
        if (res.status === 403 || res.status === 409) {
          const data = await res.json().catch(() => ({}));
          loadBoard();
          alert(
            data?.error?.message ||
              '이동할 수 없습니다. 최신 상태로 새로고침했습니다.',
          );
          return null;
        }
        if (!res.ok) return null;
        return res.json();
      })
      .then((updated) => {
        if (updated) {
          const idx = notes.findIndex((n) => n.id === noteId);
          if (idx >= 0) notes[idx] = updated;
          renderNotes();
          renderWingbarMyNotes();

          socket.emit('move_note', {
            public_id: publicId,
            note_id: noteId,
            x: x,
            y: y,
            version: updated.version
          });
        }
      })
      .catch(() => {
        note.x = previousX;
        note.y = previousY;
      });
  }

  function renderNotes() {
    $container.find('.note').remove();
    notes.forEach((note) => {
      const $el = $('<div>')
        .addClass('note')
        .css({
          left: (note.x ?? 0) + 'px',
          top: (note.y ?? 0) + 'px',
          zIndex: note.z_index ?? 0,
        })
        .attr('data-note-id', note.id)
        .attr('data-version', note.version);

      $el.append($('<div>').addClass('note-drag-handle'));
      const $body = $('<div>').addClass('note-body');
      if (note.image_url) {
        $body.append(
          $('<img>').attr('src', note.image_url).css({
            maxWidth: '100%',
            display: 'block',
            marginBottom: 4,
            borderRadius: 4,
          }),
        );
      }
      $body.append(
        $('<div>')
          .addClass('note-text')
          .text(note.text || ''),
      );
      $el.append($body);

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
          showLoginRequiredModal();
          return null;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(
            data?.error?.message || '포스트잇 생성에 실패했습니다.',
          );
        }
        return res.json();
      })
      .then((note) => {
        if (note) {
          notes.push(note);
          renderNotes();
          renderWingbarMyNotes();

          socket.emit('create_note', {
            public_id: publicId,
            note: note,
          })
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
  function openImageGuideModal() {
    $('#image-guide-modal').addClass('is-open').attr('aria-hidden', 'false');
  }
  function closeImageGuideModal() {
    $('#image-guide-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $('#btn-add-image').on('click', function (e) {
    e.stopPropagation();
    if (imageInsertMode) {
      imageInsertMode = false;
      $(this).removeClass('image-mode-active');
      closeImageModal();
    } else {
      openImageGuideModal();
    }
  });
  $(document).on('click', '#image-guide-modal .note-modal-backdrop[data-close="true"]', closeImageGuideModal);
  $('#image-guide-cancel').on('click', closeImageGuideModal);
  $('#image-guide-confirm').on('click', function () {
    closeImageGuideModal();
    imageInsertMode = true;
    $('#btn-add-image').addClass('image-mode-active');
  });

  // 윙바
  function openWingbar() {
    $('#wingbar-backdrop, #wingbar')
      .addClass('is-open')
      .attr('aria-hidden', 'false');
  }
  function closeWingbar() {
    $('#wingbar-backdrop, #wingbar')
      .removeClass('is-open')
      .attr('aria-hidden', 'true');
  }
  $('#btn-menu').on('click', openWingbar);
  $('#btn-close-wingbar').on('click', function () {
    closeWingbar();
    highlightNote(null);
  });
  $('#wingbar-backdrop').on('click', function () {
    closeWingbar();
    highlightNote(null);
  });

  $(document).on('click', '#wingbar-my-notes .wingbar-note-item', function () {
    const noteId = $(this).attr('data-note-id');
    highlightNote(noteId);
    openNoteDetailModal(noteId);
  });

  // 링크 재발급 (보드 생성자만)
  function openLinkRegenerateModal() {
    $('#link-regenerate-modal').addClass('is-open').attr('aria-hidden', 'false');
  }
  function closeLinkRegenerateModal() {
    $('#link-regenerate-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $('#wingbar-regenerate-link').on('click', function () {
    closeWingbar();
    openLinkRegenerateModal();
  });
  $(document).on('click', '#link-regenerate-modal .note-modal-backdrop[data-close="true"]', closeLinkRegenerateModal);
  $('#link-regenerate-cancel').on('click', closeLinkRegenerateModal);
  $('#link-regenerate-confirm').on('click', function () {
    const newPublicId = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
          const r = (Math.random() * 16) | 0;
          const v = c === 'x' ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        });
    const $btn = $('#link-regenerate-confirm');
    $btn.prop('disabled', true);
    fetch(`/api/boards/${publicId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public_id: newPublicId }),
    })
      .then(async (res) => {
        if (res.status === 401) { showLoginRequiredModal(); return null; }
        if (res.status === 403) { alert('보드 생성자만 링크를 변경할 수 있습니다.'); return null; }
        if (!res.ok) {
          const d = await res.json().catch(() => ({}));
          throw new Error(d?.error?.message || '링크 변경에 실패했습니다.');
        }
        return res.json();
      })
      .then((data) => {
        if (data && data.public_id) {
          closeLinkRegenerateModal();
          window.location.href = '/boards/' + data.public_id;
        }
      })
      .catch((err) => {
        $btn.prop('disabled', false);
        alert(err.message);
      });
  });

  let pendingNotePosition = null; // 더블클릭 시 생성 위치 저장 (null이면 + 버튼 경로)
  let lastMousePos = null; // 마지막 마우스 위치 (키보드로 추가 시 폴백용)

  function showLoginRequiredModal() {
    $('#login-required-modal').addClass('is-open').attr('aria-hidden', 'false');
  }
  function closeLoginRequiredModal() {
    $('#login-required-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }
  $(document).on('click', '#login-required-modal .note-modal-backdrop[data-close="true"]', closeLoginRequiredModal);
  $('#login-required-close').on('click', closeLoginRequiredModal);

  function closeNoteModal() {
    $('#note-modal').removeClass('is-open').attr('aria-hidden', 'true');
    pendingNotePosition = null;
  }

  function openNoteModal(atPosition) {
    pendingNotePosition = atPosition; // {x,y} 또는 null
    $('#note-modal').addClass('is-open').attr('aria-hidden', 'false');
    $('#note-modal-text').val('').focus();
  }

  $(document).on('mousemove', function (e) {
    lastMousePos = { clientX: e.clientX, clientY: e.clientY };
  });

  $('#btn-add-note').on('click', function () {
    openNoteModal(null);
  });
  $(document).on(
    'click',
    '.note-modal-backdrop[data-close="true"]',
    closeNoteModal,
  );
  $('#note-modal-cancel').on('click', closeNoteModal);

  $(document).on('click', '#note-modal-confirm', function (e) {
    const text = String($('#note-modal-text').val() || '').trim() || '새 메모';
    const pos = pendingNotePosition;
    closeNoteModal();
    const rect = $container[0].getBoundingClientRect();
    let x, y;
    if (pos) {
      x = Math.max(20, pos.x);
      y = Math.max(20, pos.y);
    } else {
      const getPosFromCoords = (cx, cy) => {
        if (cx === 0 && cy === 0) return null;
        const mx = cx - rect.left;
        const my = cy - rect.top;
        return mx >= 0 && mx <= rect.width && my >= 0 && my <= rect.height
          ? { x: Math.max(20, mx), y: Math.max(20, my) }
          : null;
      };
      const isKeyboardTrigger = e.detail === 0;
      const fromClick = !isKeyboardTrigger ? getPosFromCoords(e.clientX, e.clientY) : null;
      const fromLastMouse = lastMousePos ? getPosFromCoords(lastMousePos.clientX, lastMousePos.clientY) : null;
      const centerX = Math.max(20, Math.floor(window.innerWidth / 2 - rect.left - 80));
      const centerY = Math.max(20, Math.floor(window.innerHeight / 2 - rect.top - 50));
      if (fromClick) {
        x = fromClick.x;
        y = fromClick.y;
      } else if (fromLastMouse) {
        x = fromLastMouse.x;
        y = fromLastMouse.y;
      } else {
        x = centerX;
        y = centerY;
      }
    }
    createNote(x, y, text);
  });

  // 보드 빈 곳 더블클릭 → 새 포스트잇 모달 열기
  // dblclick이 보드 영역에서 미발생하는 경우가 있어, mousedown 기반 수동 감지 추가
  const DBLCLICK_DELAY = 400;
  const DBLCLICK_MOVE = 5;
  let lastBoardMousedown = { t: 0, x: 0, y: 0 };

  function tryOpenNoteModalAt(clientX, clientY) {
    if (imageInsertMode) return;
    const rect = $container[0].getBoundingClientRect();
    if (
      clientX < rect.left ||
      clientX > rect.right ||
      clientY < rect.top ||
      clientY > rect.bottom
    )
      return false;
    const x = Math.max(20, clientX - rect.left);
    const y = Math.max(20, clientY - rect.top);
    openNoteModal({ x, y });
    return true;
  }

  document.addEventListener(
    'mousedown',
    function (e) {
      if (e.button !== 0) return;
      if (
        $(e.target).closest(
          '.note, .note-modal, .note-detail-modal, .image-modal, .wingbar',
        ).length
      )
        return;
      const rect = $container[0].getBoundingClientRect();
      if (
        e.clientX < rect.left ||
        e.clientX > rect.right ||
        e.clientY < rect.top ||
        e.clientY > rect.bottom
      )
        return;
      const now = Date.now();
      if (
        now - lastBoardMousedown.t <= DBLCLICK_DELAY &&
        Math.abs(e.clientX - lastBoardMousedown.x) <= DBLCLICK_MOVE &&
        Math.abs(e.clientY - lastBoardMousedown.y) <= DBLCLICK_MOVE
      ) {
        e.preventDefault();
        e.stopPropagation();
        lastBoardMousedown = { t: 0, x: 0, y: 0 };
        tryOpenNoteModalAt(e.clientX, e.clientY);
        return;
      }
      lastBoardMousedown = { t: now, x: e.clientX, y: e.clientY };
    },
    true,
  );

  document.addEventListener(
    'dblclick',
    function (e) {
      if ($(e.target).closest('.note').length) return;
      if (
        $(e.target).closest(
          '.note-modal, .note-detail-modal, .image-modal, .wingbar',
        ).length
      )
        return;
      if (tryOpenNoteModalAt(e.clientX, e.clientY)) {
        lastBoardMousedown = { t: 0, x: 0, y: 0 };
      }
    },
    true,
  );

  // 포스트잇 더블클릭 → 수정 모달
  $container.on('dblclick', '.note', function (e) {
    if (imageInsertMode) return;
    e.stopPropagation();
    const noteId = $(e.currentTarget).attr('data-note-id');
    if (noteId) openNoteDetailModal(noteId);
  });

  // 포스트잇 드래그로 이동 (이동 8px 이상일 때만 드래그, 그 전에는 텍스트 선택 가능)
  const DRAG_THRESHOLD = 8;
  let dragging = {
    $el: null,
    noteId: null,
    startX: 0,
    startY: 0,
    startLeft: 0,
    startTop: 0,
    active: false,
  };

  // 포스트잇 상세 모달 (요구사항 4.4)
  let detailModalNoteId = null;
  let detailModalOriginalZ = null;

  function openNoteDetailModal(noteId) {
    const note = notes.find((n) => n.id === noteId);
    if (!note) return;
    detailModalNoteId = noteId;
    highlightNote(noteId);
    const $noteEl = $container.find('.note[data-note-id="' + noteId + '"]');
    if ($noteEl.length) {
      detailModalOriginalZ = $noteEl.css('z-index');
      $noteEl.css('z-index', 9999);
    }
    $('#note-detail-text').text(note.text || '(내용 없음)');
    const $img = $('#note-detail-image');
    if (note.image_url) {
      $img.attr('src', note.image_url).show();
    } else {
      $img.hide();
    }
    const isOwner = !!(
      currentUserId && String(note.owner_user_id) === String(currentUserId)
    );
    if (isOwner) {
      $('#note-detail-edit, #note-detail-delete').show();
    } else {
      $('#note-detail-edit, #note-detail-delete').hide();
    }
    $('#note-detail-view').show();
    $('#note-detail-edit-view').hide();
    $('#note-detail-modal').addClass('is-open').attr('aria-hidden', 'false');
  }

  function closeNoteDetailModal() {
    if (detailModalNoteId) {
      const $noteEl = $container.find(
        '.note[data-note-id="' + detailModalNoteId + '"]',
      );
      if ($noteEl.length && detailModalOriginalZ != null) {
        $noteEl.css('z-index', detailModalOriginalZ);
      }
    }
    detailModalNoteId = null;
    detailModalOriginalZ = null;
    highlightNote(null);
    $('#note-detail-modal').removeClass('is-open').attr('aria-hidden', 'true');
  }

  $(document).on(
    'click',
    '.note-detail-backdrop[data-close="true"]',
    closeNoteDetailModal,
  );
  $('#note-detail-close').on('click', closeNoteDetailModal);

  $(document).on('keydown', function (e) {
    if (e.key !== 'Delete' && e.key !== 'Backspace') return;
    if (!$('#note-detail-modal').hasClass('is-open')) return;
    if ($('#note-detail-edit-view').is(':visible')) return;
    if (!$('#note-detail-delete').is(':visible')) return;
    e.preventDefault();
    $('#note-detail-delete').trigger('click');
  });

  $('#note-detail-edit').on('click', function () {
    const note = notes.find((n) => n.id === detailModalNoteId);
    if (!note) return;
    $('#note-detail-edit-textarea').val(note.text || '');
    $('#note-detail-view').hide();
    $('#note-detail-edit-view').show();
  });

  $('#note-detail-cancel-edit').on('click', function () {
    $('#note-detail-edit-view').hide();
    $('#note-detail-view').show();
  });

  $('#note-detail-save').on('click', function () {
    const note = notes.find((n) => n.id === detailModalNoteId);
    if (!note) return;
    const text = $('#note-detail-edit-textarea').val() || '';
    fetch(`/api/boards/${publicId}/notes/${detailModalNoteId}`, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: note.version, text }),
    })
      .then(async (res) => {
        if (res.status === 401) {
          showLoginRequiredModal();
          return null;
        }
        if (res.status === 403 || res.status === 409) {
          const data = await res.json().catch(() => ({}));
          loadBoard();
          alert(
            data?.error?.message ||
              '수정할 수 없습니다. 최신 상태로 새로고침했습니다.',
          );
          closeNoteDetailModal();
          return null;
        }
        if (!res.ok) return null;
        return res.json();
      })
      .then((updated) => {
        if (updated) {
          const idx = notes.findIndex((n) => n.id === detailModalNoteId);
          if (idx >= 0) notes[idx] = updated;
          renderNotes();
          renderWingbarMyNotes();
          closeNoteDetailModal();

          socket.emit('update_note', {
            public_id: publicId,
            note: updated
          })
        }
      })
      .catch(() => {});
  });

  $('#note-detail-delete').on('click', function () {
    if (!confirm('이 포스트잇을 삭제할까요?')) return;
    const noteId = detailModalNoteId;
    if (!noteId) return;
    fetch(`/api/boards/${publicId}/notes/${noteId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
      .then(async (res) => {
        if (res.status === 401) {
          showLoginRequiredModal();
          return null;
        }
        if (res.status === 403 || res.status === 404) {
          const data = await res.json().catch(() => ({}));
          alert(data?.error?.message || '삭제할 수 없습니다.');
          return null;
        }
        return res.ok;
      })
      .then((ok) => {
        if (ok) {
          notes = notes.filter((n) => n.id !== noteId);
          renderNotes();
          renderWingbarMyNotes();
          closeNoteDetailModal();

          socket.emit('delete_note', {
            public_id: publicId,
            note_id: noteId,
          })
        }
      })
      .catch(() => {});
  });

  $(document).on('selectstart', function (e) {
    if (dragging.$el) e.preventDefault();
  });

  $container.on('mousedown', '.note', function (e) {
    if (imageInsertMode) return;
    if (e.button !== 0) return;
    if (!currentUserId) return; // 익명 사용자는 메모 이동 불가
    if ($(e.target).closest('.note-text').length) return;
    e.preventDefault();
    window.getSelection().removeAllRanges();
    document.body.classList.add('select-none');
    const $note = $(this);
    const noteId = $note.attr('data-note-id');
    if (!noteId) return;
    dragging = {
      $el: $note,
      noteId: noteId,
      startX: e.clientX,
      startY: e.clientY,
      startLeft: parseFloat($note.css('left')) || 0,
      startTop: parseFloat($note.css('top')) || 0,
      active: false,
    };
  });

  $(document)
    .on('mousemove', function (e) {
      if (!dragging.$el) return;

      const dx = e.clientX - dragging.startX;
      const dy = e.clientY - dragging.startY;
      if (
        !dragging.active &&
        (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)
      ) {
        dragging.active = true;
      }

      if (!dragging.active) return;

      dragging.$el.css({
        left: Math.max(0, dragging.startLeft + dx) + 'px',
        top: Math.max(0, dragging.startTop + dy) + 'px',
      });
    })
    .on('mouseup', function () {
      if (!dragging.$el) return;
      document.body.classList.remove('select-none');
      if (dragging.active) {
        const left = parseFloat(dragging.$el.css('left')) || 0;
        const top = parseFloat(dragging.$el.css('top')) || 0;
        updateNotePosition(dragging.noteId, left, top);
      }
      dragging = {
        $el: null,
        noteId: null,
        startX: 0,
        startY: 0,
        startLeft: 0,
        startTop: 0,
        active: false,
      };
    });

  // 보드 클릭 (이미지 모드만) → 이미지 삽입 UI
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

  $(document).on(
    'click',
    '.image-modal-backdrop[data-close="true"]',
    closeImageModal,
  );
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
    const file = input.files[0];

    fetch(`/api/boards/${publicId}/presigned-url`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({filename: file.name})
    }).then(async (res) => {
      if (res.status === 401) {
        showLoginRequiredModal();
        return null;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.error?.message || '업로드 URL 생성에 실패했습니다.');
      }
      return res.json()
    }).then((data) => {
      if (!data) return;

      const presignedUrlData = data.presigned_url;
      const imageKey = data.image_key;

      const formData = new FormData();

      Object.keys(presignedUrlData.fields).forEach((key) => {
        formData.append(key, presignedUrlData.fields[key]);
      });

      formData.append('Content-Type', file.type)

      formData.append('file', file);

      return fetch(presignedUrlData.url, {
        method: 'POST',
        body: formData,
      }).then((s3Res) => {
        if (!s3Res.ok) {
          throw new Error('S3 이미지 업로드에 실패했습니다.')
        }
        createNote(x, y, '', imageKey);
          closeImageModal();
          imageInsertMode = false;
          $('#btn-add-image').removeClass('image-mode-active');
      });
    })
    .catch((err) => {
      console.error(err);
      alert(err.message);
    })
  });
});
