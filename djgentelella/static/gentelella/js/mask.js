$(function () {
    function validate(instance) {
        if (instance.val().search('_')==-1 && instance.val().length>0) {
            instance.css('border-color', '#ccc');
        } else {
            instance.css('border-color', 'red');
        }
    }

    $('[data-widget="PhoneNumberMaskInput"]').blur(function (e) {
        validate($(this));
    });
  
    $('[data-widget="SerialNumberMaskInput"]').blur(function (e) {
        validate($(this));
    });
    $('[data-widget="TaxIDMaskInput"]').blur(function (e) {
        validate($(this));
    });
    $('[data-widget="CreditCardMaskInput"]').blur(function (e) {
        validate($(this));
    });
    
});