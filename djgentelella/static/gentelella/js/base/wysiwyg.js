function uploadFile(url_pages,file, editor) {
    data = new FormData();
    data.append("file", file);
    $.ajax({
        data: data,
        type: "POST",
        url: url_pages,
        cache: false,
        contentType: false,
        processData: false,
        success: function (url) {
            $(editor).summernote('editor.insertImage',(location.origin +url.link).trim());
        }
    });
}