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
        // 로그인 성공 시 메인(보드 목록) 페이지로 이동
        // TODO: 메인 페이지 구현 후 경로 수정
        window.location.href = "/";
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
