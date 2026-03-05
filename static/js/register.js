$(document).ready(function() {
    
    const $errorBox = $('#error_message');
    const $errorText = $errorBox.find('p');

    $errorBox.addClass('hidden');

    $('form').on('submit', function(e) {

        e.preventDefault(); 

        const username = $('#username').val();
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
                // console.log(xhr)
                //alert(xhr.status);
                //alert(thrownError);
                // console.error("Response JSON:", xhr.responseJSON);

                if (xhr.status === 400) {

                    showError("이미 존재하는 이름입니다.");
                }
                else if(xhr.status === 422) {
                
                    //showError(xhr.responseJSON.error)
                    showError("유효성 검사 실패");
                                
                    if (!checkValidate(username, password, pwdConfirm)) 
                        return false; 
                }

            },
        });
    });

    // 에러 띄우기
    function showError(message) {
        $errorText.text(message);
        $errorBox.removeClass('hidden');
    }

    function checkValidate(username, password, pwdConfirm){
        if (password !== pwdConfirm) {
            showError("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
            return false;
        }
        else if(username.length < 2 || username.length > 7) {
            showError("이름은 2자 이상, 7자 이하로 입력해주세요.");
            return false;
        }
        else if (password.length < 8) {
            showError("비밀번호는 적어도 8자리보다 길어야 합니다.");
            return false;
        }

        return true;
    }
});


