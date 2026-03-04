$(document).ready(function() {
    
    const $errorBox = $('#error_message');
    const $errorText = $errorBox.find('p');

    $errorBox.addClass('hidden');

    $('form').on('submit', function(e) {

        e.preventDefault(); 

        const username = $('#username').val();
        const password = $('#password').val();
        const pwdConfirm = $('#password_confirm').val();

        
        if (password !== pwdConfirm) {
            
            showError("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
            return false;
        }

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
                
            }
        });
    });

    // 에러 띄우기
    function showError(message) {
        $errorText.text(message);
        $errorBox.removeClass('hidden');
    }

});


