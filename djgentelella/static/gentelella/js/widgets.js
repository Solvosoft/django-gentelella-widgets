function grid_slider(instance) {
    let obj = $(instance[0]);

    let to = obj.attr('data-from_max');

    let from = obj.attr('data-from_min');

    if ($("input[name=" + obj.attr('data-target-to') + "]").val() > 200) {
        to = $("input[name=" + obj.attr('data-target-to') + "]").val()
    }

    if ($("input[name=" + obj.attr('data-target-from') + "]").val() > 200) {
        from = $("input[name=" + obj.attr('data-target-from') + "]").val()
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'to': to,
        'type': 'double',
        'step': obj.attr('data-step'),
        'prefix': obj.attr('data-prefix'),
        'from_fixed': obj.attr('data-from_fixed') === 'true',
        'to_fixed': obj.attr('data-to_fixed') === 'true',
        'to_max': obj.attr('data-to_max'),
        'hide_min_max': obj.attr('data-hide_min_max'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target-from') + "]").val(data.from);
            $("input[name=" + obj.attr('data-target-to') + "]").val(data.to);
            console.log(obj.attr('data-target-to'));
        }
    }
    return option;
}
function grid_slider_single(instance) {
    let obj = $(instance);


    let from = obj.attr('data_from');

    if ($("input[name=" + obj.attr('data-target') + "]").val() > 0) {
        
        from = $("input[name=" + obj.attr('data-target') + "]").val();
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'type': 'single',
        'prefix': obj.attr('data-prefix'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target') + "]").val(data.from);
            console.log($("input[name=" + obj.attr('data-target') + "]").val());
        }
    }
    return option;
}
function date_grid_slider(instance) {

    let obj = $(instance);
    let input = $("input[name=" + obj.attr('data-target') + "]").val();

    function dateToTS(date) {
        return date.valueOf();
    }

    function tsToDate(ts) {
        var lang = "en-US";
        var d = new Date(ts);

        return d.toLocaleDateString(lang, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            hour12: false,


        });
    }

    instance.ionRangeSlider({
        type: "single",
        hide_min_max: false,
        min: dateToTS(new Date(obj.attr('data_min'))),
        max: dateToTS(new Date(obj.attr('data_max'))),
        from: dateToTS(new Date(input.length>0? input : obj.attr('data_from'))),
        prettify: tsToDate,
        onChange: function (data) {
            var day = new Date(data.from);
            day = day.getFullYear() + "-" + (day.getMonth() + 1) + "-" + day.getDate() + " " + day.getHours() + ":" + day.getMinutes()
            $("input[name=" + obj.attr('data-target') + "]").val(day);
        }
    })
}
document.formset = [];
document.gtwidgets = {
    Select: function (instance) {
        instance.select2();
    },
    SelectMultiple: function (instance) {
        instance.select2();
    },
    TreeSelect: function (instance) {
        instance.select2({ templateResult: decore_select2 });
    },
    CheckboxInput: function (instance) {
        instance.iCheck({
            checkboxClass: 'icheckbox_flat-green',
            radioClass: 'iradio_flat-green'
        });
    },
    YesNoInput: function (instance) {
        instance.each(function (index, element){
             switchery = new Switchery(element, {color: '#26B99A'});
             showHideRelatedFormFields($(element));
        });
    },
    DateRangeInput: function (instance) {
        instance.daterangepicker(load_date_range(instance));
    },

    GridSlider: function (instance) {
        instance.ionRangeSlider(grid_slider(instance));
    },
    DateGridSlider: function (instance) {
        date_grid_slider(instance);
    },
    SingleGridSlider: function (instance) {
        instance.ionRangeSlider(grid_slider_single(instance));
    },
    DateRangeInputCustom: function (instance) {
        instance.daterangepicker(load_date_range_custom(instance));
    },
    RadioVerticalSelect: function (instance) {
        instance.find('input').iCheck({radioClass: 'iradio_flat-green'});
    },
    RadioHorizontalSelect: function (instance) {
        instance.find('input').iCheck({radioClass: 'iradio_flat-green'});
    },
    DateRangeTimeInput: function (instance) {
        instance.daterangepicker(load_datetime_range(instance));
    },
    TreeSelectWithAdd: function (instance) {
        instance.select2({ templateResult: decore_select2 });
    },
    TreeSelectMultiple: function (instance) {
        instance.select2({ templateResult: decore_select2 });
    },
    TreeSelectMultipleWithAdd: function (instance) {
        instance.select2({ templateResult: decore_select2 });
    },
    DateTimeInput: function (instance) {
        instance.datetimepicker();
    },
    TimeInput: function (instance) {
        instance.datetimepicker({ format: 'LT' });
    },
    DateInput: function (instance) {
        instance.datetimepicker({ format: "DD/MM/YYYY" });
    },
    Textarea: function (instance) {
        autosize(instance);
        instance.each(function (i, e) {
            if ($(e).attr('maxlength') != undefined) {
                $(e).maxlength({ alwaysShow: true, warningClass: "label label-success" });
            }
        });
    },
    PhoneNumberMaskInput: function (instance) {
        instance.inputmask({ "mask": "(999)9999-9999" });
    },
    PhoneNumberTwoDigitMaskInput: function (instance) {
        instance.inputmask({ "mask": "(99)9999-9999" });
    },
    PhoneNumberFourDigitMaskInput: function (instance) {
        instance.inputmask({ "mask": "(9999)9999-9999" });
    },
    DateMaskInput: function (instance) {
        instance.inputmask("99/99/9999", { "placeholder": "dd/mm/yyyy" });
    },
    DateTimeMaskInput: function (instance) {
        instance.inputmask("99/99/9999 99:99:99", { "placeholder": "dd/mm/yyyy HH:mm:ss" });
    },
    EmailMaskInput: function (instance) {
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
    SelectWithAdd: function (instance) {
        instance.addselectwidget();
        instance.select2();
    },
    SelectMultipleAdd: function (instance) {
        instance.addselectwidget();
        instance.select2();
    },
    TreeSelectMultipleWithAdd: function (instance) {
        instance.addselectwidget();
    },
    TreeSelectWithAdd: function (instance) {
        instance.addselectwidget();
    },
    FileInput: function (instance) {
        instance.fileuploadwidget();
    },

    GTAutocompleteSelect: function (instance) {
        build_select2_init(instance);
    },
    SerialNumberMaskInput: function (instance) {
        instance.inputmask({ "mask": "9999-9999-9999-9999-999" });
    },
    TaxIDMaskInput: function (instance) {
        instance.inputmask({ "mask": "99-99999999" });
    },
    CreditCardMaskInput: function (instance) {
        instance.inputmask({ "mask": "9999-9999-9999-9999" });
    },
    NumberKnobInput: function (instance) {
        instance.knob();
    },
    DefaultColorInput: function (instance) {
        instance.colorpicker();
    },
    StyleColorInput: function (instance) {
        instance.parent('.color-input-field').colorpicker();
    },
    HorizontalBarColorInput: function (instance) {
        instance.colorpicker({ horizontal: true });
    },
    VerticalBarColorInput: function (instance) {
        instance.colorpicker({ format: 'rgb' });
    },
    TextareaWysiwyg: function (instance) {
        new FroalaEditor("[data-widget=TextareaWysiwyg]", {
            imageUploadURL: instance.attr('data-option-image'), imageUploadParams: { "csrfmiddlewaretoken": getCookie("csrftoken") },
            fileUploadURL: instance.attr('data-option-file'),fileUploadParams: { "csrfmiddlewaretoken": getCookie("csrftoken") },
            videoUploadURL: instance.attr('data-option-file'), videoUploadParams: { "csrfmiddlewaretoken": getCookie("csrftoken") },
        });
    },
    InlinePickerColor: function (instance) {
        instance.parent('.color-input-field-inline-picker').css("display", "inline-block").colorpicker({ container: true, inline: true });
    },
    TaggingInput: function (instance) {
        instance.tagify();
    },
    EmailTaggingInput: function (instance) {
        instance.tagify({
            pattern: /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/,
        });
    },
    DJGraph: function (instance) {
        instance.gentelella_chart();
    }

}

function gt_find_initialize(instance) {
    var widgets = Object.keys(document.gtwidgets);
    widgets.forEach((widgetname) => {
        var elems = instance.find('[data-widget="' + widgetname + '"]');
        if (elems.length > 0) {
            document.gtwidgets[widgetname](elems);
        }
    });
    var autocomplete = instance.find('[data-widget="AutocompleteSelectMultiple"],[data-widget="AutocompleteSelect"]');
    if (autocomplete.length > 0) {
        document.gtwidgets['GTAutocompleteSelect'](autocomplete);
    }


}

$(document).ready(function () {
    $(".formset").each(function (index, elem) {
        document.formset.push(gtformSetManager($(elem)));
    });
});