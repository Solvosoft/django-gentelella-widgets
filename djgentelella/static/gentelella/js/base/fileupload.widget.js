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
            var $parentdiv=$this.closest('.fileupload');
            var input_token=$this.data('inputtoken');
            var obj={
                    parentdiv: $this.closest('.input-group'),
                    upload_url: $this.data('href'),
                    field_name: $this.attr('name'),
                    div_message: $parentdiv.find($this.data('message')),
                    div_process: $parentdiv.find($this.data('process')),
                    div_download: $parentdiv.find("#download_"+$this.data('inputtoken') ),
                    div_remove: $parentdiv.find("#remove_"+$this.data('inputtoken') ),
                    url_done: $this.data('done'),
                    current_icon: 'eyes',
                    input_token: input_token,
                    input_field: $parentdiv.find('input[name="'+input_token+'"]'),
                    default_value: "",
                    fileshow: $parentdiv.find('.fileshow'),
                    uploadfilecontent: $parentdiv.find('.uploadfilecontent'),
                    removecheck: $this.closest('.fileupload').find('input[data-widget="CheckboxInput"]'),
                    change_fn: function(e){
                        var parent=e;
                        return function(event){
                            let current_value=parent.input_field.val();
                            if(current_value.length==0){
                                current_value=parent.default_value;
                            }
                            try{
                                let data = JSON.parse(current_value);
                                parent.render_widget_data(data);
                            }catch(e) {
                                // do nothing
                            }

                        }
                    },
                    icon_action_toggle: function(){
                        if(this.current_icon==='eyes'){
                            this.show_upload();
                        }else{
                            this.show_eyes();
                        }
                    },
                    show_eyes:function(){
                        this.current_icon='eyes';
                        this.change_icon_file_show('fa fa-eye');
                    },
                    show_upload: function(){
                        this.current_icon='upload';
                        this.change_icon_file_show('fa fa-cloud-upload');
                    },
                    render_widget_data: function(data){
                        var parent=this;
                        if("token" in data ){
                            //data.display_name
                            parent.uploadfilecontent.hide();
                            parent.div_download.hide();
                            parent.div_remove.hide();
                            parent.div_message.show();
                            parent.div_message.html(data.display_name);
                            parent.show_upload();
                        }else if ("url" in data){
                            parent.div_download.show();
                            parent.div_remove.show();
                            parent.div_message.show();
                            parent.uploadfilecontent.hide();
                            parent.div_download.find('a')[0].href=data.url;
                            parent.div_message.html(data.display_name);
                            parent.show_upload();
                        }else{
                            parent.div_download.hide();
                            parent.div_remove.hide();
                            parent.uploadfilecontent.show();
                            parent.div_message.hide();
                            parent.show_eyes();
                        }
                    },
                    change_icon_file_show: function(touseclass){
                        this.fileshow.find('i').removeClass();
                        this.fileshow.find('i').addClass(touseclass);
                    },
                    init: function(){
                        $this.attr("required", false);
                        this.div_message.hide();
                        this.div_remove.hide();
                        var parent=this;
                        this.fileshow.on('click', function(){
                            parent.uploadfilecontent.toggle();
                            parent.div_message.toggle();
                            parent.icon_action_toggle();
                       });
                       this.input_field[0].onchange=this.change_fn(this);
                       this.default_value=this.input_field.val();
                       if(this.default_value !== ""){
                            this.input_field.trigger('change');
                       }
                       this.removecheck.on('ifToggled', function(event){
                           let current_data=JSON.parse(parent.input_field.val());
                           if(this.checked){
                                current_data['actions']="delete";
                           }else{
                            if('actions' in current_data) delete current_data.actions;
                           }
                           parent.input_field.val(JSON.stringify(current_data));
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
                                        parent.input_field.val(JSON.stringify(
                                        {'token': data.result.upload_id,
                                        'display_name': data.files[0].name }));
                                        parent.input_field.trigger('change');
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
                        this.input_field.val(JSON.stringify(item));
                        this.input_field.trigger('change');
                    }
                };
                obj.init();
            $this.data('fileUploadWidget', obj);

 });
}
