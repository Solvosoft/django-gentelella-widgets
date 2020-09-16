document.formset = [];
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
    CheckboxInput: function(instance){
        instance.iCheck({
                checkboxClass: 'icheckbox_flat-green',
                radioClass: 'iradio_flat-green'
            });
    },
    DateRangeInput: function(instance){
        instance.daterangepicker({
              timePicker: true,
              timePicker24Hour:true,
              startDate: moment().startOf('hour'),
              endDate: moment().startOf('hour').add(32, 'hour'),
              locale: {
                format: 'DD/MM/YYYY'
              }
          });
    },
    DateRangeTimeInput: function(instance){
            instance.daterangepicker({
              timePicker: true,
              timePicker24Hour:true,
              startDate: moment().startOf('hour'),
              endDate: moment().startOf('hour').add(32, 'hour'),
              locale: {
                format: 'DD/MM/YYYY HH:mm A'
              }
          });
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
    PhoneNumberTwoDigitMaskInput: function(instance){
        instance.inputmask({"mask":"(99)9999-9999"});
    },
    PhoneNumberFourDigitMaskInput: function(instance){
        instance.inputmask({"mask":"(9999)9999-9999"});
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

    GTAutocompleteSelect: function(instance){
            build_select2_init(instance);
    },
    SerialNumberMaskInput: function(instance){
        instance.inputmask({ "mask":"9999-9999-9999-9999-999"});
    },
    TaxIDMaskInput: function(instance){
        instance.inputmask({"mask":"99-99999999" });
    },
    CreditCardMaskInput: function(instance){
        instance.inputmask({"mask":"9999-9999-9999-9999" });
    },
    NumberKnobInput: function(instance){
        instance.knob();
    },
    DefaultColorInput: function(instance){
        instance.colorpicker();
    },
    StyleColorInput: function(instance){
        instance.parent('.color-input-field').colorpicker();
    },
    HorizontalBarColorInput: function(instance){
        instance.colorpicker({ horizontal: true });
    },
    VerticalBarColorInput: function(instance){
        instance.colorpicker({format: 'rgb'});
    },
    InlinePickerColor: function(instance){
        instance.parent('.color-input-field-inline-picker').css("display", "inline-block").colorpicker({container: true, inline: true });
    },
    DJGraph: function(instance){
        instance.gentelella_chart();
    }

}

function gt_find_initialize(instance){
    var widgets =Object.keys(document.gtwidgets);
    widgets.forEach((widgetname) => {
        var elems = instance.find('[data-widget="'+widgetname+'"]');
        if(elems.length>0){
            document.gtwidgets[widgetname](elems);
        }
    });
    var autocomplete = instance.find('[data-widget="AutocompleteSelectMultiple"],[data-widget="AutocompleteSelect"]');
    if(autocomplete.length > 0){
        document.gtwidgets['GTAutocompleteSelect'](autocomplete);
    }


}

$(document).ready(function(){

   $(".formset").each(function(index, elem){
        document.formset.push(gtformSetManager($(elem)));
   });
});