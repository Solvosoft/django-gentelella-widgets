$(function () {
    function getSizes(instance) {
        let result = 0;
        for (let i = 0; i < instance.val().length; i++) {
            if (instance.val().charAt(i) == "_") {
                result++;
            }
        }
        return result;
    }
    function validate_date(instance) {
        let part = instance.val().split('/');
        let date = new Date(part[2], part[1], part[0]);

        if (date == 'Invalid Date' || part[1] < 12) {
            instance.css('border-color', 'red');
        } else {
            instance.css('border-color', '#ccc');
        }
    }

    $('.mask').blur(function (e) {
        switch ($(this)[0].id) {
            case 'id_date':
                validate_date($(this));
                break;
            default:
                if (getSizes($(this)) == 0 && $(this).val().length > 0) {
                    $(this).css('border-color', '#ccc');
                } else {
                    $(this).css('border-color', 'red');

                }
                break;
        }
    });
});