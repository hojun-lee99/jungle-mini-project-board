$(document).ready(function() {
    
    const $errorBox = $('#error_message');
    const $errorText = $errorBox.find('p');

    $errorBox.addClass('hidden');

    $('form').on('submit', function(e) {

        e.preventDefault(); 

        const username = $('#id').val();
        const password = $('#password').val();
        const pwdConfirm = $('#password_confirm').val();


        if (!checkValidate(username, password, pwdConfirm)) 
            return false; 

        const requestData = {
            "username": username, // 작성자 표기용 이름
            "password": password
        }

        $.ajax({
            url: '/api/auth/register',
            type: 'POST',
            contentType: 'application/json',   
            data: JSON.stringify(requestData),  
            success: function(response) {
                alert("회원가입이 완료되었습니다!");
                
                 // 회원가입 성공 시 기본 페이지로 리다이렉트
                window.location.href = "/";
            },
            error:function(xhr) 
            {
                const serverErrorMessage = xhr.responseJSON?.error || "알 수 없는 에러가 발생했습니다.";
                showError(serverErrorMessage);
            },
        });
    });

    // 에러 띄우기
    function showError(message) {
        $errorText.text(message);
        $errorBox.removeClass('hidden');
    }

    const usernamePattern = /^[a-zA-Z0-9가-힣_]+$/;
    const passwordPattern = /^[a-zA-Z0-9!@#$%^&*()\-_]+$/;

    function checkValidate(username, password, pwdConfirm){
        if(username.length < 2 || username.length > 20) {
            showError("이름은 2자 이상 20자 이하로 입력해주세요.");
            return false;
        }
        if (!usernamePattern.test(username)) {
            showError("이름은 영문 대소문자, 숫자, 한글, _ 만 사용 가능합니다.");
            return false;
        }
        if (password.length < 8 || password.length > 50) {
            showError("비밀번호는 8자 이상 50자 이하로 입력해주세요.");
            return false;
        }
        if (!passwordPattern.test(password)) {
            showError("비밀번호는 영문 대소문자, 숫자, !@#$%^&*()-_ 만 사용 가능합니다.");
            return false;
        }
        if (password !== pwdConfirm) {
            showError("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
            return false;
        }

        return true;
    }
});


