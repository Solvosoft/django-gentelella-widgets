$.fn.fileuploadwidget = function(){
    var md5 = "",
    csrf = getCookie('csrftoken'),
    form_data = [{"name": "csrfmiddlewaretoken", "value": csrf}];
    function calculate_md5(file, chunk_size) {
        var slice = File.prototype.slice || File.prototype.mozSlice || File.prototype.webkitSlice,
          chunks = chunks = Math.ceil(file.size / chunk_size),
          current_chunk = 0,
          spark = new SparkMD5.ArrayBuffer();
        function onload(e) {
            spark.append(e.target.result);  // append chunk
            current_chunk++;
            if (current_chunk < chunks) {
                read_next_chunk();
            } else {
                md5 = spark.end();
            }
        };
        function read_next_chunk() {
            var reader = new FileReader();
            reader.onload = onload;
            var start = current_chunk * chunk_size,
            end = Math.min(start + chunk_size, file.size);
            reader.readAsArrayBuffer(slice.call(file, start, end));
        };
        read_next_chunk();
        }


        $.each($(this), function(i, e){
            var $this=$(e),
                $parentdiv=$this.closest('.input-group'),
                upload_url = $this.data('href'),
                field_name = $this.attr('name'),
                div_message = $parentdiv.find($this.data('message')),
                div_process = $parentdiv.find($this.data('process')),
                url_done = $this.data('done'),
                input_token = $this.data('inputtoken'),
                fileshow = $parentdiv.find('.fileshow'),
                uploadfilecontent = $parentdiv.find('.uploadfilecontent');

           $this.attr("required", false);
           div_message.hide();
           fileshow.on('click', function(){
                uploadfilecontent.toggle();
                div_message.toggle();
           });
           $this.fileupload({
              url: upload_url,
              dataType: "json",
              maxChunkSize: 100000, // Chunks of 100 kB
              formData: form_data,
              dropZone: $this,
              add: function(e, data) { // Called before starting upload

                div_message.empty();
                // If this is the second file you're uploading we need to remove the
                // old upload_id and just keep the csrftoken (which is always first).
                form_data.splice(1);
                calculate_md5(data.files[0], 100000);  // Again, chunks of 100 kB
                data.paramName='file';
                data.submit();
                uploadfilecontent.hide();
                div_message.show();
                div_message.html(data.files[0].name);
              },
              chunkdone: function (e, data) { // Called after uploading each chunk
                if (form_data.length < 2) {
                  form_data.push(
                    {"name": "upload_id", "value": data.result.upload_id}
                  );
                }
                 var progress = parseInt(data.loaded / data.total * 100.0, 10);
                div_process.text(  progress + "%");
              }
            }).bind('fileuploaddone', function (e, data) {
                $parentdiv.find('input[name="'+input_token+'"]').val(data.result.upload_id);
                $.ajax({
                      type: "POST",
                      url: url_done,
                      data: {
                        csrfmiddlewaretoken: csrf,
                        upload_id: data.result.upload_id,
                        md5: md5
                      },
                      dataType: "json",
                      success: function(data) {
                        div_process.html(' <i class="fa fa-check"></i>');
                      }
                });
            });
        });
}