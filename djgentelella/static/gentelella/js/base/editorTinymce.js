function upload_files(callback, meta, file, image, video) {
    var csrftoken = getCookie('csrftoken');
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    });
    var formData;
    formData = new FormData();
    formData.append('file', file, file.name);

    if (meta.filetype == 'image') {
        $.ajax({
            type: "POST",
            url: image,
            data: formData,
            dataType: "json",
            processData: false,
            contentType: false,
            success: function (response) {
                console.log(response.link);
                callback(response.link, { title: file.name });
            }
        });
    }
    if (meta.filetype == 'media') {
        $.ajax({
            type: "POST",
            url: video,
            data: formData,
            dataType: "json",
            processData: false,
            contentType: false,
            success: function (response) {
                callback(response.link, { title: file.name });
            }
        });
    }
}

// Shared TinyMCE init config for the EditorTinymce / TextareaWysiwyg widgets and
// the voice editor. Callers extend the returned object (e.g. prepend to
// `toolbar`, add a `setup`). `instance` is the jQuery textarea handle used by
// the image/video upload picker.
function gentelella_tinymce_config(instance) {
    var spellcheck = instance.attr('data-option-spellcheck') !== 'false';
    var lang = instance.attr("data-option-lang") || "en";
    return {
        browser_spellcheck: spellcheck,
        contextmenu: spellcheck ? false : 'link image table',
        menubar: false,
        toolbar: 'undo redo | bold italic underline strikethrough | fontselect fontsizeselect formatselect | alignleft aligncenter alignright alignjustify | outdent indent |  numlist bullist checklist | forecolor backcolor casechange permanentpen formatpainter removeformat | pagebreak | charmap emoticons | fullscreen  preview save print | insertfile image media pageembed template link anchor codesample | a11ycheck ltr rtl | showcomments addcomment',
        plugins: ['advlist', 'autolink', 'lists', 'link', 'image', 'charmap',
            'print', 'preview', 'anchor', 'searchreplace', 'visualblocks', 'code',
            'fullscreen', 'insertdatetime', 'media', 'table', 'paste', 'imagetools',
            'wordcount', 'codesample', 'quickbars', 'autoresize', 'hr'],
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
        paste_preprocess: function(plugin, args) {
                // Crear un DOM temporal para manipular el HTML pegado
                const div = document.createElement('div');
                div.innerHTML = args.content;

                // Buscar todas las imágenes de Twemoji (X/Twitter usa twemoji.maxcdn.com o cdn.jsdelivr.net/gh/twitter/twemoji)
                div.querySelectorAll('img[src*="twemoji"], img.emoji, img[draggable="false"][alt]').forEach(function(img) {
                  // El atributo alt contiene el emoji Unicode real
                  if (img.alt) {
                    const textNode = document.createTextNode(img.alt);
                    img.replaceWith(textNode);
                  }
                });

                args.content = div.innerHTML;
            },
    };
}
