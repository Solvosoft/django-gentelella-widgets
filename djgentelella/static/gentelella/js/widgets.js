function decore_select2 (data) {
            // We only really care if there is an element to pull classes from
            if (!data.element) {
              return data.text;
            }
            var $element = $(data.element);
            var $wrapper = $('<span></span>');
            $wrapper.addClass($element[0].className);
            $wrapper.text(data.text);
            return $wrapper;
}


document.gtwidgets = {
    Select: function (instance){
        instance.select2();
    },
    SelectMultiple: function(instance){
        instance.select2();
    },
    TreeSelect: function(instance){
        instance.select2({templateResult: decore_select2});
    },
    TreeSelectWithAdd: function(instance){
        instance.select2({templateResult: decore_select2});
    },
    TreeSelectMultiple: function(instance){
        instance.select2({templateResult: decore_select2});
    },
    TreeSelectMultipleWithAdd: function(instance){
        instance.select2({templateResult: decore_select2});
    },
    DateTimeInput: function(instance){
        instance.datetimepicker();
    },
    TimeInput: function(instance){
        instance.datetimepicker({format: 'LT'});
    },
    DateInput: function(instance){
        instance.datetimepicker({format: "DD/MM/YYYY" });
    },
    Textarea: function(instance){
        autosize(instance);
        instance.each(function(i, e){
            if($(e).attr('maxlength') != undefined){
                $(e).maxlength({alwaysShow: true, warningClass: "label label-success"});
            }
        });
    },
    PhoneNumberMaskInput: function(instance){
        instance.inputmask({"mask":"(999)9999-9999"});
    },
    DateMaskInput: function(instance){
        instance.inputmask( "99/99/9999",{ "placeholder": "dd/mm/yyyy" });
    },
    DateTimeMaskInput: function(instance){
        instance.inputmask( "99/99/9999 99:99:99",{ "placeholder": "dd/mm/yyyy HH:mm:ss" });
    },
    EmailMaskInput: function(instance){
        instance.inputmask({
            mask: "*{1,20}[.*{1,20}][.*{1,20}][.*{1,20}]@*{1,20}[.*{2,6}][.*{1,2}]",
            greedy: false,
            onBeforePaste: function (pastedValue, opts) {
              pastedValue = pastedValue.toLowerCase();
              return pastedValue.replace("mailto:", "");
            },
            definitions: {
              '*': {
                validator: "[0-9A-Za-z!#$%&'*+/=?^_`{|}~\-]",
                casing: "lower"
              }
            }
          });
    },
    SelectWithAdd: function(instance){
        instance.addselectwidget();
        instance.select2();
    },
    SelectMultipleAdd: function(instance){
        instance.addselectwidget();
        instance.select2();
    },
    TreeSelectMultipleWithAdd: function(instance){
        instance.addselectwidget();
    },
    TreeSelectWithAdd: function(instance){
        instance.addselectwidget();
    },
    FileInput: function(instance){
        instance.fileuploadwidget();
    },
    AutocompleteSelectMultiple: function(instance){
        if(typeof build_select2_init == 'function') {
            build_select2_init(instance);
        }
    },
    AutocompleteSelect: function(instance){
        if(typeof build_select2_init == 'function') {
            build_select2_init(instance);
        }
    },
    SerialNumberMaskInput: function(instance){
        instance.inputmask({ "mask":"9999-9999-9999-9999-999"});
    },
    CustomMaskInput: function(instance){
        instance.inputmask({"mask":"99-999999" });
    },
    TaxIDMaskInput: function(instance){
        instance.inputmask({"mask":"99-99999999" });
    },
    CreditCardMaskInput: function(instance){
        instance.inputmask({"mask":"9999-9999-9999-9999" });
    },

}

function gt_find_initialize(instance){
    var widgets =Object.keys(document.gtwidgets);
    widgets.forEach((widgetname) => {
        document.gtwidgets[widgetname](instance.find('[data-widget="'+widgetname+'"]'));
    });
}