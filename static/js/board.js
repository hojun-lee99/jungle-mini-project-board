$(document).ready(function () {
  // 공유 버튼 클릭 이벤트
  $('#btn-share').on('click', function () {
    alert('현재 보드의 링크가 클립보드에 복사되었습니다. (구현 필요)');
  });

  // 이미지 추가 버튼 클릭 이벤트
  $('#btn-add-image').on('click', function () {
    console.log('이미지 업로드 모달을 엽니다.');
  });

  // 햄버거 메뉴 클릭 이벤트
  $('#btn-menu').on('click', function () {
    console.log('사이드바 메뉴를 엽니다.');
  });

  // 보드 빈 공간을 더블 클릭하면 새 글 작성하기
  $('#board-container').on('dblclick', function (e) {
    // 클릭한 위치 (x, y 좌표)
    const x = e.pageX;
    const y = e.pageY;
    console.log(`[${x}, ${y}] 위치에 새 글 쓰기 창을 엽니다.`);
  });
});
