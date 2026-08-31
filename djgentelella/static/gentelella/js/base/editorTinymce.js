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
        // Required from TinyMCE 8 on: without it the editor loads read-only.
        // 'gpl' is the self-hosted open source licence, which is what this
        // package ships under.
        license_key: 'gpl',
        // The "Upgrade" button the cloud build promotes itself with.
        promotion: false,
        browser_spellcheck: spellcheck,
        contextmenu: spellcheck ? false : 'link image table',
        menubar: false,
        // Trimmed to buttons that exist. The 5.x toolbar still listed
        // checklist, casechange, permanentpen, formatpainter, pageembed,
        // template, a11ycheck, showcomments and addcomment, which are premium
        // and were drawing nothing, and `print`, whose plugin is gone --
        // printing is the browser's. fontselect/fontsizeselect/formatselect
        // were renamed in 6.
        toolbar: 'undo redo | bold italic underline strikethrough | fontfamily fontsize blocks | alignleft aligncenter alignright alignjustify | outdent indent | numlist bullist | forecolor backcolor removeformat | pagebreak | charmap emoticons | fullscreen preview save | image media link anchor codesample | ltr rtl',
        plugins: ['advlist', 'autolink', 'lists', 'link', 'image', 'charmap',
            'preview', 'anchor', 'searchreplace', 'visualblocks', 'code',
            'fullscreen', 'insertdatetime', 'media', 'table', 'wordcount',
            'codesample', 'quickbars', 'autoresize', 'pagebreak', 'emoticons',
            // ltr/rtl come from this one; the 5.x config asked for the buttons
            // without ever loading the plugin that provides them.
            'directionality'],
        // `hr` is a core toolbar button since 6, not a plugin.
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
        paste_preprocess: function(editor, args) {
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


/* Start TinyMCE on every textarea in a jQuery set.
 *
 * TinyMCE 8 dropped jquery.tinymce.min.js from the package -- the jQuery
 * integration is a separate project now -- so `$(el).tinymce(config)` is
 * `tinymce.init({target: el, ...})`.
 */
function gentelella_tinymce_init(instance, config) {
    instance.each(function (index, element) {
        tinymce.init($.extend({}, config, {target: element}));
    });
}
