$(document).ready(function () {
    var accordions = bulmaAccordion.attach();
    viewDownload();
    init_editor();
    let i = 0;
    $('.grids').keyup(function (e) {
        grid($(this));
    });

    $(".drag").sortable({
        connectWith: '.column',
        handle: '.bb'
    });


    $(".sidebar").draggable({
        helper: "clone",
        connectToSortable: ".drag, .column",
        handle: '.bb',
        stop: function (e, ui) {
            cleandrag($(ui.helper));
            $('.drag, .drag .column').sortable({
                connectWith: '.drag, .column',
                handle: '.bb',

                over: function () {
                    $(this).addClass('op');
                },
                out: function () {
                    $(this).removeClass('op');
                }
            });
        }
    });

    $(".components").draggable({
        helper: "clone",
        connectToSortable: ".drag",
        handle: '.bb',
        stop: function (e, ui) {
            cleancomponent($(ui.helper));
            $('.drag, .drag .column').sortable({
                connectWith: '.column',
                handle: '.bb',

                over: function () {
                    $(this).addClass('op');
                },
                out: function () {
                    $(this).removeClass('op');
                }
            });
        }
    });

    $('.drag').droppable({
        drop: function (e, ui) {
            if ($(ui.draggable).find('.editor').length) {
                $(ui.draggable).find('.editor').attr('onClick', '$(this).focus()');
                $(ui.draggable).find('.editor').attr('id', 'mc' + i);
                init_editor('mc' + i);
                i++;
            }
        }

    });

    function init_editor(id) {
        tinymce.init({
            selector: '#' + id,
            menubar: false,
            inline: true,
            toolbar: false,
            skin: 'oxide-dark',
            plugins: [
                'autolink',
                'codesample',
                'link',
                'lists',
                'hr',
                'hr pagebreak',
                'media',
                'quickbars',
                "advlist autolink lists link image charmap print preview anchor",
                "searchreplace visualblocks code fullscreen",
                "insertdatetime media table paste imagetools wordcount",
            ],
            quickbars_selection_toolbar: 'bold italic underline | undo redo | fontselect fontsizeselect | forecolor backcolor | alignleft aligncenter alignright alignfull |numlist bullist| hr| link image',
        });
    }
    function cleandrag(component) {
        component.removeAttr('style');
        component.css('padding', '5px');
        component.find('.b_delete').css('display', 'inline-block');
        component.find('.coll').removeAttr('style');
        component.css('padding-bottom', '10px')
        component.find('input').remove();
    }

    function cleancomponent(component) {
        component.removeAttr('style');
        component.css('padding', '10px');
        component.find('.b_delete').css('display', 'inline-block');
        component.find('.content').removeAttr('style');
        component.find('label').remove();
    }

    $("#files").click(function () {
        var pages = new Blob([exportpdf()], { type: "text/plain;charset=utf-8" });
        downloadpages(pages, "example.html");
    });
    btn_actions();


});


function downloadpages(content, filename) {
    var reader = new FileReader();
    reader.onload = function (event) {
        var save = document.createElement('a');
        save.href = event.target.result;
        save.target = '_blank';
        save.download = filename;
        var clicEvent = new MouseEvent('click', {
            'view': window,
            'bubbles': true,
            'cancelable': true
        });
        save.dispatchEvent(clicEvent);
        (window.URL || window.webkitURL).revokeObjectURL(save.href);
    };
    reader.readAsDataURL(content);
};

function validate_grids(data) {
    let cols = data.val().split(" ");
    let acum = 0;
    $.each(cols, function (i, e) {
        if (e != "") {
            acum += parseInt(e);
        }
    });
    if (acum == 12) {
        data.parent().find('.bb').css('display', 'inline-block');
    } else {
        data.parent().find('.bb').css('display', 'none');
    }
    return cols;
}

function btn_actions() {
    $(document).on('click', '.b_delete', function () {
        $(this).parent().remove();
    });
}
function datas() {
    x = $('.drag').clone();
    x.find('.b_delete').remove()
    x.find('.bb').remove()
    x.find('.editor').removeAttr('contenteditable style onclick spellcheck');

    return x;
}
function grid(sizes) {
    a = '';
    $.each(validate_grids(sizes), function (i, e) {
        a += `<div class="column is-${e}">
            </div>`
    });
    a += `</div>`;
    sizes.parent().find('.coll').html(a);
}


function viewDownload() {
    $("#files").removeClass("is-hidden");
}

function exportpdf() {
    data = ` <!DOCTYPE html>
<html lang="en">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><link href="{% static 'vendors/font-awesome/font-awesome.min.css' %}" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma-accordion@2.0.1/dist/css/bulma-accordion.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css"><title>Document</title>
</head><style>
.columns .cols{
    padding: 25px;
}
.parag{
padding: 10px;
}
.b_delete{
    display:none !important;
}
</style>
<body>`+ datas().html();
    data += `</body>

</html>`;
    return data;
}