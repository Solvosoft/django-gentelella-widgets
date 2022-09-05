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