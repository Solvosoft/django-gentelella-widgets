$.fn.fileuploadwidget = function(){
    var csrf = getCookie('csrftoken');
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
                    removecheck: $this.closest('.fileupload').find(
                        'input[data-widget="CheckboxInput"]'),
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
                    set_progress: function(percent){
                        // A percentage inside a 3rem chip was the only sign an
                        // upload was running; the bar reads it from here.
                        $parentdiv.toggleClass('gt-uploading', percent < 100);
                        $parentdiv[0].style.setProperty(
                            '--gt-upload-progress', percent + '%');
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
                       this.removecheck.on('change', function(event){
                           let current_data=JSON.parse(parent.input_field.val());
                           if(this.checked){
                                current_data['actions']="delete";
                           }else{
                            if('actions' in current_data) delete current_data.actions;
                           }
                           parent.input_field.val(JSON.stringify(current_data));
                       });
                       $this.on('change', function () {
                           var file = this.files && this.files[0];
                           if (!file) { return; }
                           parent.div_message.empty();
                           parent.uploadfilecontent.hide();
                           parent.div_message.show();
                           parent.div_message.html(file.name);
                           gt_chunked_upload({
                               file: file,
                               url: parent.upload_url,
                               done_url: parent.url_done,
                               csrf: csrf,
                               onprogress: function (percent) {
                                   parent.div_process.text(percent + '%');
                                   parent.set_progress(percent);
                               }
                           }).then(function (upload_id) {
                               parent.set_progress(100);
                               parent.input_field.val(JSON.stringify(
                                   {'token': upload_id, 'display_name': file.name}));
                               parent.input_field.trigger('change');
                               parent.div_process.html(' <i class="fa fa-check"></i>');
                           }).catch(function (error) {
                               parent.set_progress(100);
                               parent.resetEmpty();
                               Swal.fire(
                                   gettext('Problem in the Internet?'),
                                   error.message,
                                   'error'
                               );
                           });
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
