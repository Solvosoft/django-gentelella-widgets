$(document).ready(function () {
    bulmaAccordion.attach();

    var $toggle = $('#nav-toggle');
    var $menu = $('#nav-menu');

    $toggle.click(function () {
        $(this).toggleClass('is-active');
        $menu.toggleClass('is-active');
    });

    init_editor();

    let i = 0;
    $('.grids').keyup(function (e) {
        grid($(this));
    });
    //botones de arriba
    $('#view').click(function (e) {
        preview('none', 'white');

    });
    $('#edit').click(function (e) {
        edit_content('block', '#4a4a4a');
    });
    //mover componentes
    $(".drag").sortable({
        connectWith: '.column',
        handle: '.move'
    });

    //jalar grids
    $(".sidebar").draggable({
        helper: "clone",
        connectToSortable: ".drag, .column",
        handle: '.move',
        stop: function (e, ui) {
            cleandrag($(ui.helper));
            $('.drag, .drag .column').sortable({ //movimiento interno de grid
                connectWith: '.drag, .column', //que lugares desplazarse
                handle: '.move',
            });
        }
    });

    $(".components").draggable({
        helper: "clone",
        connectToSortable: ".drag",
        handle: '.move',
        stop: function (e, ui) {
            cleancomponent($(ui.helper));
            $('.drag, .drag .column').sortable({
                connectWith: '.column',
                handle: '.move',
            });
        }
    });

    $('.drag').droppable({
        drop: function (e, ui) {
            if ($(ui.draggable).find('.editor').length) {
                $(ui.draggable).find('.editor').attr('onClick', '$(this).focus()');
                $(ui.draggable).find('.editor').attr('id', 'mc' + i);
                i++;
                init_editor();
            }
        }

    });



    $("#files").click(function () {
        var pages = new Blob([exportpdf()], { type: "text/plain;charset=utf-8" });
        downloadpages(pages, "Document.html");
    });
    btn_actions();


});

function init_editor() {
    $('.editor').tinymce({
        menubar: false,
        inline: true,
        toolbar: false,
        skin: 'oxide-dark',
        plugins: ['autolink', 'codesample', 'link', 'lists', 'media', 'quickbars',
            "advlist autolink lists link image charmap print preview anchor",
            "searchreplace visualblocks code fullscreen",
            "insertdatetime media table paste imagetools wordcount" ,
            "autoresize", "hr",
        ],
        quickbars_selection_toolbar: 'bold italic underline | undo redo | fontselect fontsizeselect | forecolor backcolor | alignleft aligncenter alignright alignfull |numlist bullist| link image|autoresize|hr',
    });
}
function cleandrag(component) {
    component.removeAttr('style');
    component.find('.b_delete').css('display', 'inline-block');
    component.find('.move').css('line-height', '20px');
    component.find('.coll').removeAttr('style');
    component.css('padding-bottom', '20px');
    component.find('input').remove();
}

function cleancomponent(component) {
    component.removeAttr('style');
    component.find('.b_delete').css('display', 'inline-block');
    component.find('.content').removeAttr('style');
    component.find('label').remove();
}

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
        data.parent().find('.move').css({ 'display': 'inline-block', 'line-height': '30px' });
    } else {
        data.parent().find('.move').css('display', 'none');
    }
    return cols;
}

function btn_actions() {
    $(document).on('click', '.b_delete', function () {
        $(this).parent().remove();
    });
}
function pages() {
    x = $('.drag').clone();
    x.find('.b_delete').remove()
    x.find('.move').remove()
    x.find('div').removeClass('coll')
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

function preview(display, color) {
    $('.menu-side').css('display', display);
    $('#main-content').css('display', display);
    let x = document.createElement('div');
    $(x).addClass('view container');
    $(x).append(pages().html());
    $('.main').append(x);
    $('body').css('background-color', color);
}
function edit_content(display, color) {
    $('.menu-side').css('display', display);
    $('#main-content').css('display', display);
    $('.main').find('.view').remove();
    $('body').css('background-color', color);
}
function exportpdf() {
    data = ` <!DOCTYPE html>
<html lang="en">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"><link href="{% static 'vendors/font-awesome/font-awesome.min.css' %}" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma-accordion@2.0.1/dist/css/bulma-accordion.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css"><title>Document</title>
</head>
<style></style>
<body><div class="container">`+ pages().html() + `</div></body></html>`;
    return data;
}