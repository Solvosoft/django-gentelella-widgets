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
        instance.each(function (index, element) {
            switchery = new Switchery(element, { color: '#26B99A' });
            showHideRelatedFormFields($(element));
        });
    },
    DateRangeInput: function (instance) {
        instance.daterangepicker(load_date_range(instance));
    },

    DateRangeInputCustom: function (instance) {
        instance.daterangepicker(load_date_range_custom(instance));
    },
    RadioVerticalSelect: function (instance) {
        instance.find('input').iCheck({ radioClass: 'iradio_flat-green' });
    },
    RadioHorizontalSelect: function (instance) {
        instance.find('input').iCheck({ radioClass: 'iradio_flat-green' });
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
        instance.datetimepicker({
             format : "YYYY-MM-DD HH:mm"
        });
    },
    TimeInput: function (instance) {
        instance.datetimepicker({ format: 'HH:mm' });
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
        instance.inputmask("99/99/9999 99:99", { "placeholder": "dd/mm/yyyy HH:mm",
         format: "YYYY-MM-DD HH:mm"});
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

    },

    EditorTinymce: function (instance) {
        $(instance).removeAttr('required');
        instance.tinymce({
            menubar: false,
            toolbar: 'undo redo | bold italic underline strikethrough | fontselect fontsizeselect formatselect | alignleft aligncenter alignright alignjustify | outdent indent |  numlist bullist checklist | forecolor backcolor casechange permanentpen formatpainter removeformat | pagebreak | charmap emoticons | fullscreen  preview save print | insertfile image media pageembed template link anchor codesample | a11ycheck ltr rtl | showcomments addcomment',
            plugins: ['autolink', 'codesample', 'link', 'lists', 'media', 'quickbars', "advlist autolink lists link image charmap print preview anchor",
                "searchreplace visualblocks code fullscreen","insertdatetime media table paste imagetools wordcount",
                "autoresize", "hr", "image",
            ],
            quickbars_insert_toolbar: 'quicktable | hr pagebreak',
            file_picker_callback: function (callback, value, meta) {
                var input = document.createElement('input');
                input.setAttribute('type', 'file');
                input.setAttribute('accept', 'image/*');
                input.onchange = function () {
                    var file = this.files[0];
                    upload_files(callback, meta, file, instance.attr('data-option-image'), 
                    instance.attr('data-option-video'));
                };
                input.click();
            },
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