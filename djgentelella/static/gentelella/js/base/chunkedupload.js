/* Chunked uploads, spoken straight to djgentelella.chunked_upload.
 *
 * Replaces blueimp jQuery-File-Upload, which brought three files with it --
 * itself, the jQuery UI widget factory it is built on, and an iframe transport
 * that exists for browsers without XHR file upload, meaning IE9. What is left
 * of that group is spark-md5, which is here for a reason no browser API covers:
 * SubtleCrypto cannot hash incrementally, so the alternative to it is reading
 * the whole file into memory before uploading it.
 *
 * The protocol is the server's, in `chunked_upload/views.py`:
 *
 *   - POST each slice as multipart `file`, with `Content-Range: bytes a-b/n`
 *     and, after the first answer, the `upload_id` it returned. The view
 *     rejects a slice whose start is not exactly the offset it has stored, so
 *     the slices go up strictly in order, one at a time.
 *   - POST `upload_id` + `md5` to the completion url. The view rejects the
 *     upload if either is missing or the checksum does not match.
 *
 * That last rule is why the hash is awaited before the upload starts rather
 * than computed alongside it: the old code kicked off a FileReader chain and
 * submitted at once, so a small file on a fast connection finished uploading
 * while `md5` was still the empty string, and the completion request came back
 * "Both 'upload_id' and 'md5' are required".
 */

/* 100 kB, which is what this widget has always used. */
var GT_UPLOAD_CHUNK_SIZE = 100000;


/* md5 of a File, hashed slice by slice so the file is never held in memory. */
function gt_file_md5(file, chunk_size) {
    return new Promise(function (resolve, reject) {
        var spark = new SparkMD5.ArrayBuffer();
        var chunks = Math.ceil(file.size / chunk_size);
        var current = 0;

        function read_next() {
            var reader = new FileReader();
            reader.onerror = function () {
                reject(new Error(gettext('The file could not be read')));
            };
            reader.onload = function (event) {
                spark.append(event.target.result);
                current++;
                if (current < chunks) {
                    read_next();
                } else {
                    resolve(spark.end());
                }
            };
            var start = current * chunk_size;
            reader.readAsArrayBuffer(
                file.slice(start, Math.min(start + chunk_size, file.size)));
        }

        if (chunks === 0) {          // an empty file still has a checksum
            resolve(spark.end());
            return;
        }
        read_next();
    });
}


/* Upload `file` in slices and mark it complete.
 *
 * options: {file, url, done_url, csrf, chunk_size, onprogress}
 * Resolves with the server's `upload_id`; rejects with an Error whose message
 * is what the server said, ready to show to the person who tried.
 */
function gt_chunked_upload(options) {
    var chunk_size = options.chunk_size || GT_UPLOAD_CHUNK_SIZE;
    var file = options.file;
    var upload_id = null;

    function fail(response, body) {
        // The view answers errors as {detail: "..."}; anything else (a proxy
        // timing out, a 500 page) has no json to read.
        var detail = body && body.detail ? body.detail : response.statusText;
        return new Error(detail || ('HTTP ' + response.status));
    }

    function post(url, form) {
        return fetch(url, {
            method: 'POST', body: form, credentials: 'same-origin',
            headers: options.headers || {}
        });
    }

    function send_chunk(start) {
        var end = Math.min(start + chunk_size, file.size);
        var form = new FormData();
        form.append('csrfmiddlewaretoken', options.csrf);
        // The filename has to travel with the slice: the view takes the name
        // of the upload from the first chunk it receives.
        form.append('file', file.slice(start, end), file.name);
        if (upload_id) {
            form.append('upload_id', upload_id);
        }

        return fetch(options.url, {
            method: 'POST',
            body: form,
            credentials: 'same-origin',
            headers: {
                // end is inclusive, hence the -1; an empty file is 0-0/0.
                'Content-Range': 'bytes ' + start + '-' +
                    Math.max(end - 1, 0) + '/' + file.size
            }
        }).then(function (response) {
            return response.json().catch(function () {
                return null;
            }).then(function (body) {
                if (!response.ok) {
                    throw fail(response, body);
                }
                upload_id = body.upload_id;
                if (options.onprogress) {
                    options.onprogress(
                        Math.round(end / Math.max(file.size, 1) * 100));
                }
                if (end < file.size) {
                    return send_chunk(end);   // strictly sequential: the view
                }                             // checks start against its offset
                return upload_id;
            });
        });
    }

    return gt_file_md5(file, chunk_size).then(function (md5) {
        return send_chunk(0).then(function () {
            var form = new FormData();
            form.append('csrfmiddlewaretoken', options.csrf);
            form.append('upload_id', upload_id);
            form.append('md5', md5);
            return post(options.done_url, form).then(function (response) {
                return response.json().catch(function () {
                    return null;
                }).then(function (body) {
                    if (!response.ok) {
                        throw fail(response, body);
                    }
                    return upload_id;
                });
            });
        });
    });
}
