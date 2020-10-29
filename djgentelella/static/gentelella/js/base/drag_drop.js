$(document).ready(function () {
    var accordions = bulmaAccordion.attach();


    $(".bb").draggable({
        helper: "clone",
        cursor: "pointer",
        zIndex: 101,

    });



    $(".drag").droppable({
        accept: ".bb",
        drop: function (event, ui) {
            $(this).append(components(ui.draggable[0].id));
            viewDownload();
        }
    }).sortable({
        cursor: "move",
        helper: function (evt, ui) {
            return $(ui).clone().appendTo($(this)).show();

        }
    });
    $("#files").click(function () {
        var pages = new Blob([exportpdf()], { type: "text/plain;charset=utf-8" });
        downloadpages(pages, "example.html");
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

});


function components(options) {
    let result = "";
    switch (options) {
        case 'nav-1':
            result = navbar()
            break;
        case 'col-8-4':
            result = grid([8, 4]);
            break;
        case 'col-6-6':
            result = grid([6, 6]);
            break;
        case 'col-4-4-4':
            result = grid([4, 4, 4]);
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
    a = `<div class="container"> <div class="columns ui-sortable-handle is-centered is-vcentered cols has-background-white">`;
    for (let i = 0; i < sizes.length; i++) {
        a += `<div class="column is-${sizes[i]}  ui-droppable ui-sortable  p-3">
            <p contenteditable="true" onclick='$(this).focus();'>   Lorem ipsum dolor sit amet consectetur adipisicing elit. Voluptatum, non dolorum eveniet cupiditate quia voluptatem sunt a repellat fugit? Quaerat quae facilis dignissimos aliquam necessitatibus deserunt, explicabo soluta suscipit? Mollitia?</p></div> `
    }
    a += `</div> </div>`;
    return a;
}

function paragraph() {
    return `<div class="container p-3 has-background-white"><p contenteditable="true"onclick='$(this).focus();'>Lorem ipsum dolor sit amet consectetur adipisicing elit. Maxime tempora vitae itaque quod iure, nobis culpa totam, voluptatem voluptates necessitatibus molestiae. Nostrum sit vel magni omnis nisi dicta incidunt ipsam?</p></div>`;
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
.cols{
padding: 10px;
margin-top: 5px;
}
.parag{
padding: 10px;
}
</style>
<body>`+ $('.drag').html();
    data += `</body>

</html>`;
    return data;
}