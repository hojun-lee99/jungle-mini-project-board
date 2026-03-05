$(document).ready(function () {
  // 로그인 처리
  $("#login-form").submit(function (e) {
    e.preventDefault();

    const username = $("#username").val();
    const password = $("#password").val();
    const $error = $("#login-error");

    $error.addClass("hidden").text("");

    $.ajax({
      url: "/api/auth/login",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ username: username, password: password }),
      xhrFields: { withCredentials: true },
      success: function (data) {
        // 로그인 성공 시 next 파라미터가 있으면 해당 페이지로, 없으면 메인으로 리다이렉트
        const params = new URLSearchParams(window.location.search);
        const next = params.get('next');
        const target = next && next.startsWith('/') && !next.startsWith('//') ? next : '/main';
        window.location.href = target;
      },
      error: function (xhr) {
        const msg = xhr.responseJSON?.error || "로그인에 실패했습니다.";
        $error.removeClass("hidden").text(msg);
      },
    });
  });

  // 회원가입 버튼 - 회원가입 페이지로 이동
  $("#register-btn").click(function () {
    // TODO: 회원가입 페이지 경로 구현 후 수정
    window.location.href = "/register";
  });
});
