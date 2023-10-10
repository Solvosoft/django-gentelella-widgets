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
            var $this=$(e);
            var $parentdiv=$this.closest('.input-group');
            var obj={
                    parentdiv: $this.closest('.input-group'),
                    upload_url: $this.data('href'),
                    field_name: $this.attr('name'),
                    div_message: $parentdiv.find($this.data('message')),
                    div_process: $parentdiv.find($this.data('process')),
                    div_download: $parentdiv.find("#download_"+$this.data('inputtoken') ),
                    div_remove: $parentdiv.find("#remove_"+$this.data('inputtoken') ),
                    url_done: $this.data('done'),
                    input_token: $this.data('inputtoken'),
                    fileshow: $parentdiv.find('.fileshow'),
                    uploadfilecontent: $parentdiv.find('.uploadfilecontent'),
                    removecheck: $this.closest('.fileupload').find('input[data-widget="CheckboxInput"]'),
                    init: function(){
                        $this.attr("required", false);
                        this.div_message.hide();
                        var parent=this;
                        this.fileshow.on('click', function(){
                            parent.uploadfilecontent.toggle();
                            parent.div_message.toggle();
                       });
                       this.removecheck.on('ifToggled', function(event){
                           if(this.checked){
                                parent.parentdiv.find('input[name="'+parent.input_token+'"]').val("0");
                           }else{
                             if( parent.parentdiv.find('input[name="'+parent.input_token+'"]').val() == "0"){
                                parent.parentdiv.find('input[name="'+parent.input_token+'"]').val("");
                             }
                           }
                       });
                            $this.fileupload({
                                  url: parent.upload_url,
                                  dataType: "json",
                                  maxChunkSize: 100000, // Chunks of 100 kB
                                  formData: form_data,
                                  dropZone: $this,
                                  add: function(e, data) { // Called before starting upload

                                    parent.div_message.empty();
                                    // If this is the second file you're uploading we need to remove the
                                    // old upload_id and just keep the csrftoken (which is always first).
                                    form_data.splice(1);
                                    calculate_md5(data.files[0], 100000);  // Again, chunks of 100 kB
                                    data.paramName='file';
                                    data.submit();
                                    parent.uploadfilecontent.hide();
                                    parent.div_message.show();
                                    parent.div_message.html(data.files[0].name);
                                  },
                                  chunkdone: function (e, data) { // Called after uploading each chunk
                                    if (form_data.length < 2) {
                                      form_data.push(
                                        {"name": "upload_id", "value": data.result.upload_id}
                                      );
                                    }
                                     var progress = parseInt(data.loaded / data.total * 100.0, 10);
                                    parent.div_process.text(  progress + "%");
                                  }
                                }).bind('fileuploaddone', function (e, data) {
                                        parent.parentdiv.find('input[name="'+parent.input_token+'"]').val(data.result.upload_id);
                                        $.ajax({
                                              type: "POST",
                                              url: parent.url_done,
                                              data: {
                                                csrfmiddlewaretoken: csrf,
                                                upload_id: data.result.upload_id,
                                                md5: md5
                                              },
                                              dataType: "json",
                                              success: function(data) {
                                                parent.div_process.html(' <i class="fa fa-check"></i>');
                                              }
                                        });
                                   }).bind('fileuploadchunkfail', function (e, data) {
                                   parent.resetEmpty();
                                   Swal.fire(
                                            gettext('Problem in the Internet?'),
                                            data.errorThrown,
                                            'error'
                                            );
                                   });
                                },
                    resetEmpty: function(){
                        this.div_message.html("");
                        this.div_message.hide();
                        this.div_download.hide();
                        this.div_remove.hide();
                        this.uploadfilecontent.show();
                    },
                    addRemote: function(item){
                        this.parentdiv.find('input [name="'+this.field_name+'"]').val(item.name);
                        this.div_download.find('a')[0].href=item.url;
                        this.div_message.html(item.name);
                        this.div_message.show();
                        this.div_download.show();
                        this.div_remove.show();
                        this.uploadfilecontent.hide();
                    }

                };
                obj.init();
            $this.data('fileUploadWidget', obj);

 });
}
