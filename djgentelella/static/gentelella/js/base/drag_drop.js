$(document).ready(function () {
    var drop = false;
    var accordions = bulmaAccordion.attach();

    $('.grids').keyup(function (e) {
        validate_grids($(this));
    });



    viewDownload();

    $(".drag, .cols").sortable({
        connectWith: '.cols, .drag',
        opacity: 0.35,
        receive: function (e, ui) {
            if ($(ui.helper).hasClass('btn-grid')) {
                $(this).append(grid($(ui.item).parent().next().find('input')));
            } else {
                $(this).append(components(ui.item.attr('id')));
            }
            if ($(ui.helper).hasClass('bb')) {
                ui.helper.remove();
            }
        },

        over: function () {
            $(this).addClass('op');
            drop = true;
            if (drop) {
                $('.drag').height($('.drag').height() + 200);
            }
            drop = false;
        },
        out: function () {
            $(this).removeClass('op');

        }
    });

    $(document).on('click', '.dropdown .button', function () {
        var dropdown = $(this).parents('.dropdown');
        dropdown.toggleClass('is-active');
        dropdown.focusout(function () {
            $(this).removeClass('is-active');
        });
    });

    $(document).on('click', '.dropdown-item', function () {
        cleanAling($(this));
    });

    $(".bb").draggable({
        helper: "clone",
        connectToSortable: ".drag, .cols",

        stop: function (e, ui) {

            $('.drag .cols').sortable({
                opacity: 0.35,
                connectWith: '.cols,.drag',
                receive: function (e, ui) {
                    if ($(ui.helper).hasClass('bb')) {
                        ui.helper.remove();
                    }
                    $(this).append(components(ui.item.attr('id')));

                },

                over: function () {
                    $(this).addClass('op');
                },
                out: function () {
                    $(this).removeClass('op');
                }
            });
        }
    });

    $("#files").click(function () {
        var pages = new Blob([exportpdf()], { type: "text/plain;charset=utf-8" });
        downloadpages(pages, "example.html");
    });
    btn_actions();


});

function cleanAling(data) {
    var component = data.parent().parent().parent().parent().parent().parent().find('p');
    var list = ['has-text-centered', 'has-text-right', 'has-text-left'];
    list.forEach(element => {
        console.log(element);
        if (component.hasClass(element)) {
            component.removeClass(element);
        }
    });
    component.addClass(data.attr('rel'));

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
        data.parent().prev().find('span').css('display', 'inline-block');
    } else {
        data.parent().prev().find('span').css('display', 'none');
    }
    return cols;
}

function btn_actions() {


    $(document).on('click', '.b_delete', function () {
        $(this).parent().remove();
    });

    $(document).on('mouseenter', '.b_delete', function (event) {
        $(this).css('opacity', '1');
    }).on('mouseleave', '.b_delete', function (event) {
        $(this).css('opacity', '0.2');
    });
}
function datas() {
    x = document.createElement('div');
    aux = document.createElement('div');
    x = $('.drag');
    x.each(function (element) {
        $(this).removeClass('ui-sortable');
        if ($(this).attr('contenteditable')) {
            $(this).removeAttr('contenteditable');
        }
    });
    return x;
}
function components(options) {
    let result = "";
    switch (options) {
        case 'nav-1':
            result = navbar()
            break;

        case 'text':
            result = paragraph();
            break;
        default:
            break;
    }
    return result;
}

function navbar() {
    return `<nav class="navbar is-primary" role="navigation" aria-label="main navigation"><div class="navbar-brand">
<a class="navbar-item" href="https://bulma.io"><img src="https://bulma.io/images/bulma-logo.png" width="112" height="28">
</a><a role="button" class="navbar-burger burger" aria-label="menu" aria-expanded="false" data-target="navbarBasicExample">
<span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span></a>
</div><div id="navbarBasicExample" class="navbar-menu"><div class="navbar-start">
<a class="navbar-item">Home</a><a class="navbar-item">Documentation</a>
<div class="navbar-item has-dropdown is-hoverable"><a class="navbar-link">More</a><div></nav>`;
}
function grid(sizes) {
    console.log(validate_grids(sizes));
    a = `<div class="columns row is-centered has-background-white"><button class="b_delete button is-small is-rounded is-danger">x</button>`;
    $.each(validate_grids(sizes), function (i, e) {

        a += `<div class="column is-${e} has-background-danger cols">
  
            </div>`
    });
    a += `</div>`;
    return a;
}

function paragraph() {

    return `
  
    <div class="has-background-white parag">
    <div class="dropdown">
    <div class="dropdown-trigger"><a class="button" aria-haspopup="true" aria-controls="dropdown-menu">
      <span>Aling</span> <span class="icon is-small"><i class="fas fa-angle-down" aria-hidden="true"></i></span></a>
      <div class="dropdown-menu" id="dropdown-menu" role="menu">
      <div class="dropdown-content">
        <a href="#" class="dropdown-item" rel="has-text-left">
          left
        </a>
        <a href="#" class="dropdown-item" rel="has-text-right">
          right
        </a>
        <a href="#" class="dropdown-item" rel="has-text-centered">
          center
        </a>
    </div>
    </div>
    </div>
    </div>

      <a class="b_delete button is-small is-rounded is-danger level-item" aria-label="like">X</a>
  <p contenteditable="true"onclick='$(this).focus();'>Lorem ipsum dolor sit amet consectetur adipisicing elit. Maxime tempora vitae itaque quod iure, nobis culpa totam, voluptatem voluptates necessitatibus molestiae. Nostrum sit vel magni omnis nisi dicta incidunt ipsam?</p></div>`;
}

function viewDownload() {
    $("#files").removeClass("is-hidden");
}

function exportpdf() {
    data = ` <!DOCTYPE html>
<html lang="en">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="{% static 'vendors/font-awesome/font-awesome.min.css' %}" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma-accordion@2.0.1/dist/css/bulma-accordion.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.1/css/bulma.min.css">

<title>Document</title>
</head>
<style>
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
    console.log(datas().html());
    return data;
}