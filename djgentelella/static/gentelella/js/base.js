(function($){

$.fn.notificationWidget = function(){

    update_instance = function(url, pk){
        $.ajax({
            url: url+pk,
            data: {'state': 'hide'},
            type: "PUT",
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            success: function(){ },
            error: function(error){
                console.log(error);
            }
        });
    }
    delete_instance = function(url, pk){
        $.ajax({
            url: url+pk,
            //data: form.serialize(),
            type: "DELETE",
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            success: function(){ },
            error: function(error){
                console.log(error);
            }
        });
    }
    on_click_clk =  function(base, elem, parent, instance){

        return function(event){

              instance.do_not_hide = true;
              var action = $(this).data('action');
              if('hide' == action){
                parent.update_instance(instance.data('apiurl'),  elem.id);
              }
              if( 'delete' == action){
                parent.delete_instance(instance.data('apiurl'), elem.id);
              }
              base.remove();
              var count = parseInt(instance.find('.notificacionnumero').text());
              count -= 1;
              instance.find('.notificacionnumero').text(count);

        }
    }
    create_notification = function(instance, elem){
        var datedata =  moment(elem.creation_date, document.date_format).fromNow()
        var base = $("#temp_"+instance.attr('id')).html();
        base = base.replace('$id', elem.id).replace('$message_type', elem.message_type);
        base = base.replace('$link', elem.link).replace('$description', elem.description);
        base = base.replace('$datedata', datedata);
        base = '<li class="nitem">'+base+'</li>';
        var jbase = $(base);
        var clk = jbase.find('.clk');
        clk.on('click', this.on_click_clk(jbase, elem, this, instance))
        $("#showall_"+instance.attr('id')).before(jbase);
    }
    dropdown_actions = function(instance){
        instance.do_not_hide=false;
        $(document).on("hide.bs.dropdown", function (e) {
            if (instance.attr('id') == e.relatedTarget.id){
                if(instance.do_not_hide){
                    e.stopPropagation();
                    e.preventDefault();
                    instance.do_not_hide=false;
                }
            }
        });
    }
    set_next_prev = function(instance, data){
            if(data.next == null){
                let next = $("#next_"+instance.attr('id'));
                next.data('url', 'false');
                next.hide();
            }else{
                let next = $("#next_"+instance.attr('id'));
                next.data('url', data.next);
                next.show();
            }
            if(data.previous == null){
                let previous = $("#prev_"+instance.attr('id'));
                previous.data('url', 'false');
                previous.hide();
            }else{
                let previous = $("#prev_"+instance.attr('id'));
                previous.data('url', data.previous);
                previous.show();
            }
    }
    remove_notifications = function(instance){
        $("#ddm_"+instance.attr('id')+' .nitem').remove();
    }
    next_prev_action = function(instance){
        f = function(){
               instance.do_not_hide = true;
               var url = $(this).data('url');
               if(url != 'false'){
                    remove_notifications(instance);
                    load_notifications(instance, url);
               }
        }
        $("#prev_"+instance.attr('id')).on('click', f);
        $("#next_"+instance.attr('id')).on('click', f);

    }
    function load_notifications(instance, base_url){

        $.getJSON(base_url, function(data){
                instance.find('.notificacionnumero').text( data.count);
                for(var x=0; x<data.results.length; x++){
                    create_notification(instance, data.results[x]);
                }
                set_next_prev(instance, data);
        });

    }
    set_css_size = function(instance){
        var data = $('#ddm_'+instance.attr('id'));
        data.css({
        'max-height': $(window).height()-($(window).height()*0.2), 'overflow': 'auto'});
    }
    $.each($(this), function(i, e){
        let instance = $(e);
        let base_url = instance.data('apiurl');
        dropdown_actions(instance);
        moment.locale(instance.data('lang'));
        set_css_size(instance);
        load_notifications(instance, base_url);
        next_prev_action(instance);
    });
}


document.chartcallbacks = {
   doughnutlabels: function (item, data) {

        var label = data.datasets[item.datasetIndex].label;
        var value = data.datasets[item.datasetIndex].data[item.index];
        return label + ': ' + value;
    },
   doughnutbeforeLabel: function(tooltipItem, chart){
        return chart.datasets[tooltipItem.datasetIndex]['label']
    }
}
$.fn.gentelella_chart = function(){

   check_callbacks=function(result){
        if(result.options && result.options.tooltips && result.options.tooltips.callbacks){
           var cback = result.options.tooltips.callbacks;
           if(cback.label){
                if(document.chartcallbacks.hasOwnProperty(cback.label)){
                    result.options.tooltips.callbacks.label = document.chartcallbacks[cback.label]
                }
           }
          if(cback.beforeLabel){
                if(document.chartcallbacks.hasOwnProperty(cback.beforeLabel)){
                    result.options.tooltips.callbacks.beforeLabel = document.chartcallbacks[cback.beforeLabel]
                }
          }
        }
       return result
   }

   $.each($(this), function(i, e){
    var url = $(e).data('url');
    var canvas = $(e).find('canvas');
    $.ajax({
        url: url,
        type : "GET",
        dataType : 'json',
        success : function(result) {
           var ctx = canvas[0].getContext('2d');
           var myChart = new Chart(ctx, check_callbacks(result));

        },
        error: function(xhr, resp, text) {
           console.log(text);
        }
    });
   });
}

$.fn.listcrudrest = function(){
   $.each($(this), function(i, e){
    var $this=$(e),
       btn = $this.find('.additemcrudlist'),
       form = $this.find('form'),
       url_add = form.attr('action'),
       del_btn =  $this.find('.gencruddel'),
       def_url = del_btn.data('href'),
       list = $this.find('.gencrudlist');
    var template = '<li> <p><div class="icheckbox_flat-green"  >'+
       '<input type="checkbox" class="flat gencrudcheck" name="__ID__" >'+
       '<ins class="iCheck-helper" ></ins></div> __DESCRIPTION__</p></li>';


    var update_list = function(result){
        var html='';
        for(var x=0; x<result.length; x++){
            html += template.replace('__ID__', result[x].id).replace(
            '__DESCRIPTION__', result[x].name);
        }

        list.find('input').iCheck({
            checkboxClass: 'icheckbox_flat-green',
            radioClass: 'iradio_flat-green'
        });
        list.html(html);
    }
    $(btn).on('click', function(){
        $(form).closest('.card').find('.alert').remove();
        $.ajax({
            url: url_add, // url where to submit the request
            type : "POST", // type of action POST || GET
            dataType : 'json', // data type
            data : $(form).serialize(), // post data || get data
            success : function(result) {
                form.find('p.error').remove();
                update_list(result);
                form[0].reset();
                $(document).trigger('crudlistadd', [form, result]);
            },
            error: function(xhr, resp, text) {
                form.find('p.error').remove();
                if(xhr.status == 400 ){
                    keys = Object.keys(xhr.responseJSON)

                    $.each(keys, function(i, e){
                        var item = form.find('*[name='+e+']');
                        item.after('<p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p>');

                        if(e == 'non_field_errors'){
                            form.before('<div class="alert"><p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p></div>');
                        }

                    });
                }
            }
        });
    });

    $(del_btn).on('click', function( ){
        var todelete=[];
        $(list).find('input:checked').each(function (i,e){
            todelete.push(e.name)
        });

        $.ajax({
            url: def_url, // url where to submit the request
            type : "DELETE", // type of action POST || GET
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            dataType : 'json', // data type
            data : { 'delitems':  todelete}, // post data || get data
            success : function(result) { update_list(result); },
            error: function(xhr, resp, text) {
                console.log(xhr, resp, text);
            }
        });
    });
    });
};
$.fn.addselectwidget = function(){
    //var e=this;
    $.each(this, function(i,e){
    $(document.body).append( $($(e).data('modalname')).detach() );
    var $modalui = $($(e).data('modalname'));
    $modalui.on('show.bs.modal', function (event) {
        var modal = $(this);
        $.ajax({
            url: modal.data('url'), // url where to submit the request
            type : "GET", // type of action POST || GET
            dataType : 'json', // data type
            success : function(result) {
                modal.find('.modal-body').html(result['message']);
                modal.find('.modal-header p').html(result['title']);
                if(result.hasOwnProperty('script')){
                    eval(result['script'])
                }

            },
            error: function(xhr, resp, text) {
                console.log(xhr, resp, text);
            }
        });
    });
    $($(e).data('modalname')+' .btnsubmit').on('click', function(){
        var form = $($(e).data('modalname')+' form');
        $.ajax({
            url: $modalui.data('url'), // url where to submit the request
            type : "POST", // type of action POST || GET
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            dataType : 'json', // data type
            data : $(form).serialize(), // post data || get data
            success : function(result) {
                if(result.ok){
                    var data = {
                    'id': result.id,
                    'text': result.text
                    }
                    var newOption = new Option(data.text, data.id, false, true);
                     $(e).append(newOption).trigger('change');

                    $modalui.find('.modal-body').html("");
                    $modalui.modal('hide');
                }else{
                    $modalui.find('.modal-body').html(result['message']);
                    $modalui.find('.modal-header p').html(result['title']);
                    if(result.hasOwnProperty('script')){
                       eval(result['script'])
                    }
                }
            },
            error: function(xhr, resp, text) {
                if(xhr.status == 400 ){
                    keys = Object.keys(xhr.responseJSON)

                    $.each(keys, function(i, e){
                        var item = form.find('*[name='+e+']');
                        item.after('<p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p>');
                    });
                }
            }
        });
    });
    $modalui.modal('hide');
});

}

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


function extract_select2_context(context, instance){
    let data=instance.data();
    let dropdownparent=data.dropdownparent;
    let placeholder=data.placeholder;
    let theme = data.theme;
    if( dropdownparent != undefined){
        context.dropdownParent = $(dropdownparent);
    }
    if( placeholder != undefined){
        context.placeholder=placeholder;
    }
    if(theme != undefined){
        context.theme=theme;
    }else{
        context.theme='bootstrap-5'
    }
    let template = data.templateresult;
    if(template != undefined){
        context.templateResult=window[template];
        context.templateSelection=window[template];
    }
}

function add_selected_option(item, data){
    if(!data.selected) return;

    itemjq = $(item.id);
    if (itemjq.find("option[value='" + data.id + "']").length) {
        itemjq.find("option[value='" + data.id + "']").attr('selected', 'selected');

    } else {
        // Create a DOM Option and pre-select by default
        var newOption = new Option(data.text, data.id, true, true);
        // Append it to the select
        itemjq.append(newOption).trigger('change');
    }
}
function get_selected_values(obj){
    var data = [];
    $.each(obj, function(i, e){
        if(e.value != "") data.push(e.value);
    });
    return data.join(',');
}

function get_s2filter_parameters(elemid, params){
    let filters = {
        selected: get_selected_values($(elemid).find(':selected')),
        page: params.page || 1,
    };
    if ( params.term != undefined){
        filters['term']=params.term;
    }
    $.each($(elemid).data(), function(key, value) {
        if (key.startsWith("s2filter")){
            filters[key.replace("s2filter", "").toLowerCase()] = $(value).val();
        }
    });
    return filters;
}

window.extract_select2_context=extract_select2_context;
$.fn.select2related = function(action, relatedobjs=[]) {
    /**
        [{ 'id': '#myfield',
          'url': '/myendpoint', * ignored on simple
          'start_empty': true   * only on related action
        }]
    **/
        this.relatedobjs = relatedobjs;
        let parent = this;


        if(action === "simple"){
            for(let x=0; x<this.relatedobjs.length; x++){
                let contexts2={};
                extract_select2_context(contexts2, $(this.relatedobjs[x]['id']));
                this.relatedobjs[x]['s2']=$(this.relatedobjs[x]['id']).select2(contexts2);
            }
        }

        if(action === 'remote'){
            for(let x=0; x<this.relatedobjs.length; x++){
                let contexts2={
                      placeholder: gettext('Select an element'),
                      ajax: {
                        url: this.relatedobjs[x]['url'],
                        type: 'GET',
                        dataType: 'json',
                        processResults: function (data, params) {
                            for(let rx=0; rx<data.results.length; rx++){
                                add_selected_option(parent.relatedobjs[x], data.results[rx]);
                            }
                            return data;
                        },
                        data: function (params) {
                            let filters = get_s2filter_parameters($(parent.relatedobjs[x]['id']), params);
                            $(parent.relatedobjs[x]['id']).trigger('relautocompletedata', filters);
                            return filters;
                        }
                      }
                };
                extract_select2_context(contexts2, $(this.relatedobjs[x]['id']));
                this.relatedobjs[x]['s2']=$(this.relatedobjs[x]['id']).select2(contexts2);

            }
        }
        if(action === "related"){
            for(let x=1; x<this.relatedobjs.length; x++){
                let contexts2={
                  placeholder: gettext('Select an element'),
                  ajax: {
                    url: this.relatedobjs[x]['url'],
                    type: 'GET',
                    dataType: 'json',
                    processResults: function (data, params) {
                        for(let rx=0; rx<data.results.length; rx++){
                            add_selected_option(parent.relatedobjs[x], data.results[rx]);
                        }
                        return data;
                    },
                    data: function (params) {
                      let filters = get_s2filter_parameters($(parent.relatedobjs[x]['id']), params);
                      filters['relfield']= get_selected_values($(parent.relatedobjs[x-1]['id']).find(':selected'));
                      $(parent.relatedobjs[x]['id']).trigger('relautocompletedata', filters);
                      return filters;
                    },
                  }
                };
                extract_select2_context(contexts2, $(this.relatedobjs[x]['id']));
                let newselect = $(this.relatedobjs[x]['id']).select2(contexts2);
                this.relatedobjs[x]['s2'] = newselect;
                if(parent.relatedobjs[x]['start_empty']){
                    newselect.val(null).trigger('change');
                }
            }
            let contexts2empty = {
              placeholder: gettext('Select an element'),
              ajax: {
                url: parent.relatedobjs[0]['url'],
                type: 'GET',
                dataType: 'json',
                processResults: function (data, params) {
                    for(let rx=0; rx<data.results.length; rx++){
                            add_selected_option(parent.relatedobjs[0], data.results[rx]);
                    }
                    return data;
                },
                data: function (params) {
                      let filters = get_s2filter_parameters($(parent.relatedobjs[0]['id']), params);
                      $(parent.relatedobjs[0]['id']).trigger('relautocompletedata', filters);
                      return filters;
                },
              }
            };
            extract_select2_context(contexts2empty, $(this.relatedobjs[0]['id']));
            let newselect = $(this.relatedobjs[0]['id']).select2(contexts2empty);
            this.relatedobjs[0]['id']=newselect;
            if(this.relatedobjs[0]['start_empty']){
                newselect.val(null).trigger('change');
            }
        }
        return this;
    };

})(jQuery)

function convertFileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
            const base64String = reader.result.split(',')[1];
            resolve(base64String);
        };

        reader.onerror = (error) => {
            reject(error);
        };

        reader.readAsDataURL(file);
    });
}

async function obtainFormAsJSON(form, prefix = '', extras = {}, format = true) {
    const fields = form.elements;
    const formData = {};
    // typeof variable === 'function'
    for (let key in extras) {
        if (typeof extras[key] === 'function') {
            formData[key] = extras[key](form, key, prefix);
        } else {
            formData[key] = extras[key];
        }
    }

    for (let i = 0; i < fields.length; i++) {
        const field = fields[i];

        if (field.type !== 'submit' && field.type !== 'button') {
            const fieldName = field.name.replace(prefix, '');
            if (field.type === 'textarea') {
                formData[fieldName] = $(field).val();
            } else if (field.type === 'checkbox') {
                formData[fieldName] = field.checked;
            } else if (field.type === 'radio') {
                if (field.checked) {
                    formData[fieldName] = $(field).val();
                }
            } else if (field.type === 'file') {
                const files = Array.from(field.files);
                const filesBase64 = [];

                for (let j = 0; j < files.length; j++) {
                    const file = files[j];
                    try {
                        const base64String = await convertFileToBase64(file);
                        filesBase64.push({name: file.name, value: base64String});
                    } catch (error) {
                        console.error('Error converting file:', error);
                    }
                }

                formData[fieldName] = filesBase64;
            } else if (field.multiple) {
                const selectedOptions = Array.from(field.selectedOptions);
                const selectedValues = selectedOptions.map((option) => option.value);
                formData[fieldName] = selectedValues;
            } else {
                formData[fieldName] = field.value;
            }
        }
    }

    if (format) {
        return JSON.stringify(formData);
    }

    return formData;
}

function convertToStringJson(form, prefix = "", extras = {}, format = true) {
    return obtainFormAsJSON(form[0], prefix, extras, format);
}

function load_errors(error_list, obj, parentdiv) {
    ul_obj = "<ul class='errorlist form_errors d-flex justify-content-center'>";
    error_list.forEach((item) => {
        ul_obj += "<li>" + item + "</li>";
    });
    ul_obj += "</ul>"
    $(obj).parents(parentdiv).prepend(ul_obj);
    return ul_obj;
}

function form_field_errors(target_form, form_errors, prefix, parentdiv) {
    var item = "";
    for (const [key, value] of Object.entries(form_errors)) {
        item = " #id_" + prefix + key;
        if (target_form.find(item).length > 0) {
            load_errors(form_errors[key], item, parentdiv);
        }
    }
}

function response_manage_type_data(instance, err_json_fn, error_text_fn) {
    return function (response) {
        const contentType = response.headers.get("content-type");
        if (response.ok) {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            } else {
                return response.text();
            }
        } else {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                response.json().then(data => err_json_fn(instance, data));
            } else {
                response.text().then(data => error_text_fn(instance, data));
            }
            return Promise.resolve(false);
        }

        return Promise.reject(response);  // then it will go to the catch if it is an error code
    }
}

function clear_action_form(form) {
    // clear switchery before the form reset so the check status doesn't get changed before the validation
    $(form).find("input[data-switchery=true]").each(function () {
        if ($(this).prop("checked")) {  // only reset it if it is checked
            $(this).trigger("click").prop("checked", false);
        }
    });
    $(form).find('[data-widget="TaggingInput"],[data-widget="EmailTaggingInput"]').each(function (i, e) {
        var tg = $(e).data().tagify;
        if(tg != undefined){
           tg.removeAllTags();
        }

    });
    $(form).find('[data-widget="FileChunkedUpload"],[data-widget="FileInput"]').each(function (i, e) {
        var tg = $(e).data().fileUploadWidget;
        tg.resetEmpty();
    });
    $(form).trigger('reset');
    $(form).find("select option:selected").prop("selected", false);
    $(form).find("select").val(null).trigger('change');
    $(form).find("ul.form_errors").remove();
    $(form).find(".file-link").remove();
}

var gt_form_modals = {}
var gt_detail_modals = {}
var gt_crud_objs = {};

function updateInstanceValuesForm(form, name, value) {
    var item = form.find(
        'input[name="' + name + '"], ' +
        'textarea[name="' + name + '"], ' +
        'select[name="' + name + '"]'
    );
    item.each(function (i, inputfield) {
        let done = false;
        inputfield = $(inputfield);

        if (inputfield.attr('class') === "chunkedvalue") {
            if (value) {
                var chunked = form.find('input[name="' + name + '_widget"]').data('fileUploadWidget');
                chunked.addRemote(value);
            }
            done = true;
        } else if (inputfield.attr('type') === 'file') {
            if (value) {
                var newlink = document.createElement('a');
                newlink.href = value.url;
                newlink.textContent = value.name;
                newlink.target = "_blank";
                newlink.classList.add("link-primary");
                newlink.classList.add("file-link");
                newlink.classList.add("d-block");
                inputfield.before(newlink)
            }
            done = true;
        } else if (inputfield.attr('type') === "checkbox") {
            if (inputfield.data().widget === "YesNoInput") {
                inputfield.prop("checked", !value);
                inputfield.trigger("click");
                done = true;
            } else {
                inputfield.prop("checked", value);
            }
            done = true;
        } else if (inputfield.attr('type') === "radio") {
            var is_icheck = inputfield.closest('.gtradio').length > 0;
            var sel = inputfield.filter(function () {
                return this.value === value.toString()
            });
            if (sel.length > 0) {
                sel.prop("checked", true);
                if (is_icheck) {
                    sel.iCheck('update');
                    sel.iCheck('check');
                }

            } else {
                inputfield.prop("checked", false);
                if (is_icheck) {
                    inputfield.iCheck('update');
                    inputfield.iCheck('uncheck');
                }
            }
            done = true;
        }
        if (inputfield.data().widget === "EditorTinymce" || inputfield.data().widget === "TextareaWysiwyg") {
            tinymce.get(inputfield.attr('id')).setContent(value);
            done = true;
        }
        if (inputfield.data().widget === "TaggingInput" || inputfield.data().widget === "EmailTaggingInput") {
            var tagifyelement = inputfield.data().tagify;
            if(tagifyelement!=undefined){
                tagifyelement.removeAllTags();
                tagifyelement.loadOriginalValues(value);
            }
            done = false;
        }


        // New code for testing  (*** start ***)
        // data loading in select, autocompleteselect, autocompletemultiselect
        else if (inputfield.is('select') && inputfield.data().widget === "Select") {
            inputfield.val(value).trigger('change');
            done = true;
        } else if (inputfield.is('select') && inputfield.data().widget === "AutocompleteSelect") {
            let data = value;

            if (data) {
                let newOption = new Option(data.text, data.id, true, true);
                inputfield.append(newOption).trigger('change');
            }

            done = true;
        } else if (inputfield.is('select') && inputfield.data().widget === "AutocompleteSelectMultiple") {

            if (Array.isArray(value)) {
                value.forEach(item => {
                    let newOption = new Option(item.text, item.id, true, true);
                    inputfield.append(newOption);
                });
                inputfield.trigger('change');
            }
            done = true;
        }
        // New code for testing  (*** end ***)

        if (!done) {
            inputfield.val(value);
        }
    });
}

function updateInstanceForm(form, data) {
    for (let key in data) {
        if (data.hasOwnProperty(key)) {
            updateInstanceValuesForm(form, key, data[key])
        }
    }
}


function gtforms(index, manager, formList, extra = true) {
    return {
        index: index,
        order: index,
        deleted: false,
        manager: manager,
        formList: formList,
        extra: extra,
        instance: null,
        deleteForm: function () {
            if (!this.manager.validateDeleteForm()) {
                this.manager.notify('error', 'You can not delete this form, minimum form validation failed')
                return;
            }
            this.deleted = true;
            this.instance.hide();
            this.instance.find('input[name="' + this.manager.prefix + '-' + this.index + '-DELETE"]').prop("checked", true);
            this.manager.deleteForm(this.order);
        },
        render: function () {
            var html = this.manager.template.replace(/__prefix__/gi, this.index);
            this.instance = $(html);
            formList.append(this.instance);
            this.initializeWidgets(this.instance);
            this.registerBtns();

        },
        reorder: function (oper) {
            var brother = this.manager.getForm(this.order + oper);
            this.manager.switchFrom(this.order, this.order + oper);
            if (brother != null) {
                if (oper == 1) {
                    this.instance.before(brother.instance);
                } else {
                    brother.instance.before(this.instance);
                }
            }
        },
        registerBtns: function () {
            this.instance.find('.deletebtn').on('click', this.callDelete(this));
            // down increment order and up decrement order when forms are inserted in bottom
            this.instance.find('.btndown').on('click', this.callReorder(this, 1));
            this.instance.find('.btnup').on('click', this.callReorder(this, -1));
        },
        callDelete: function (instance) {
            return () => {
                instance.deleteForm()
            };
        },
        initializeWidgets: function (instance) {
            gt_find_initialize(instance);
        },
        callReorder: function (instance, oper) {
            return () => {
                instance.reorder(oper)
            }
        },
        updateOrder: function () {
            this.instance.find('input[name="' + this.manager.prefix + '-' + this.index + '-ORDER"]').val(this.order);
        }
    }
}

function gtformSetManager(instance) {
    var obj = {
        index: 0,
        TOTAL_FORMS: 0,
        INITIAL_FORMS: 0,
        MAX_NUM_FORMS: -1,
        MIN_NUM_FORMS: -1,
        validateMax: false,
        validateMin: false,
        activeForms: 0,
        forms: [],
        instance: instance,
        formsetControl: instance.find('.formsetcontrol'),
        formList: instance.find('.formlist'),
        template: '',
        prefix: 'form-',
        initialize: function () {
            this.template = this.formsetControl.find(".formsettemplate").contents()[0].data;
            this.prefix = this.formsetControl.data('prefix');
            this.validateMax = this.formsetControl.data('validate-max') == '1';
            this.validateMin = this.formsetControl.data('validate-min') == '1';
            this.loadManagementForm();
            this.instance.find('.formsetadd').on('click', this.addBtnForm(this));
            this.addFormDom();
        },
        addBtnForm: function (instance) {
            return (e) => {
                instance.addEmtpyForm(e)
            };
        },
        addEmtpyForm: function (e) {
            if (this.validateAddForm()) {
                this.activeForms += 1;
                var form = gtforms(this.index, this, this.formList);
                form.render();
                this.forms.push(form);
                this.addForm(this, form, true, e);
                this.index += 1;
                this.updateTotalForms(+1);
            } else {
                this.notify('error', 'You cannot add new form, limit is exceded')
            }
        },
        addForm: function (parent, object, isempty, event) {
        },
        addFormDom: function () {
            this.formList.children().each((i, element) => {
                this.activeForms += 1;
                var form = gtforms(this.index, this, this.formList, extra = false);
                form.instance = $(element);
                form.registerBtns();
                this.forms.push(form);
                this.addForm(this, form, false, null);
                this.index += 1;
            });
        },
        delForm: function (parent, index, form) {
        },
        deleteForm: function (index) {
            if (!this.validateDeleteForm()) return;
            this.activeForms = Math.max(0, this.activeForms - 1);

            if (index >= 0 && index < this.forms.length) {
                this.delForm(this, index, this.forms[index]);
                if (this.forms[index].extra) {
                    this.forms.splice(index, 1);
                    this.updateTotalForms(-1);
                    if (index == this.forms.length) {
                        this.index -= 1;
                    } else {
                        for (var x = 0; x < this.forms.length; x++) {
                            this.forms[x].order = x;
                            this.forms[x].updateOrder();
                        }
                    }
                }

            }
        },
        validateAddForm: function () {
            if (!this.validateMax) return true;
            return this.MAX_NUM_FORMS == -1 || this.TOTAL_FORMS < this.MAX_NUM_FORMS;
        },
        validateDeleteForm: function () {
            if (!this.validateMin) return true;
            return this.MIN_NUM_FORMS == -1 || this.TOTAL_FORMS > this.MIN_NUM_FORMS;
        },
        loadManagementForm: function () {
            this.TOTAL_FORMS = parseInt(this.formsetControl.find('input[name="' + this.prefix + '-TOTAL_FORMS"]').val());
            this.INITIAL_FORMS = parseInt(this.formsetControl.find('input[name="' + this.prefix + '-INITIAL_FORMS"]').val());
            this.MIN_NUM_FORMS = parseInt(this.formsetControl.find('input[name="' + this.prefix + '-MIN_NUM_FORMS"]').val());
            this.MAX_NUM_FORMS = parseInt(this.formsetControl.find('input[name="' + this.prefix + '-MAX_NUM_FORMS"]').val());
        },
        updateManagementForm: function () {
            this.formsetControl.find('input[name="' + this.prefix + '-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
            this.formsetControl.find('input[name="' + this.prefix + '-INITIAL_FORMS"]').val(this.INITIAL_FORMS);
            this.formsetControl.find('input[name="' + this.prefix + '-MIN_NUM_FORMS"]').val(this.MIN_NUM_FORMS);
            this.formsetControl.find('input[name="' + this.prefix + '-MAX_NUM_FORMS"]').val(this.MAX_NUM_FORMS);
        },
        updateTotalForms: function (oper) {
            this.TOTAL_FORMS = this.TOTAL_FORMS + oper;
            this.formsetControl.find('input[name="' + this.prefix + '-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
        },
        getForm: function (index) {
            if (index >= 0 && index < this.forms.length) {
                return this.forms[index];
            }
            return null;
        },
        switchFrom: function (fref, fswap) {
            var freform = this.getForm(fref);
            var fswapform = this.getForm(fswap);
            if (freform != null && fswapform != null) {
                var tmporder = freform.order;
                freform.order = fswapform.order;
                fswapform.order = tmporder;
                freform.updateOrder();
                fswapform.updateOrder();

                this.forms.sort((a, b) => a.order - b.order);
                this.redrawOrdering();
            }

        },
        redrawOrdering: function () {
            for (var x = 0; x < this.forms.length; x++) {
                this.formList.append(this.forms[x].instance);
            }
        },
        notify: function (type, text) {
            console.log(text);
        },
        clean: function () {
            while (this.forms.length > 0) {
                var f = this.forms.pop();
                f.instance.remove();
            }
            this.TOTAL_FORMS = 0;
            this.INITIAL_FORMS = 0;
            this.TOTAL_FORMS = 0;
            this.index = 0;
            this.updateManagementForm();
        }
    }
    obj.initialize();
    return obj;
}



class HelperBox {
    constructor(instance,box, configs){
        this.instance = instance
        this.box = box;
        this.configs = configs;
        $("#modal_"+instance+"_btn").on('click', this.send_edit_data(this));
        this.add_tool_active = false;
        this.add_commands_toolbar();
        this.hide_edit_button();
        let widthx='50%';
        if($(window).width() < 502){
            widthx='90%';
        }

        $("#content_"+this.instance).css(
        {'position': 'fixed',
        'bottom':  '35px', 'left': '50px', 'width': widthx, 'z-index': 10000});
        $(".btnsavedel").on('click', this.delete_element_save(this));
    }
    /**
    this.configs ={
    help_url: "/api/ayuda/"
    id_view: "agresion-p1"
    permissions: Object { "djgentelella.add_help": true, "djgentelella.change_help": true, "djgentelella.view_help": true }
    }
    */
    hide_palette(){
        $("#content_"+this.instance).collapse('hide');
    }
    hide_elements(){
        $("#helper-body").find(".helperitem").hide();
    }
    show_elements(){
        $("#helper-body").find(".helperitem").show();
    }
    hide_edit_button(){
       if(!(this.has_perm('djgentelella.change_help')|| this.has_perm('djgentelella.delete_help'))){
            $("#expand_"+this.instance).hide();
       }
       if(!this.has_perm('djgentelella.add_help')){
           $("#show_help_"+this.instance).hide();
       }


    }

    get_help_list(hide=false){
        let parent = this;
        $.getJSON(this.configs.help_url+"?id_view="+this.configs.id_view,
            function(data){
                for(var i=0; i < data.length; i++){
                    parent.add_element(data[i]);
                }
                if(hide){
                    parent.hide_elements()
                }
            } );
    }
    delete_element_save(parent){
        return function(){
            var pk = $('.formdelitem input[name="pk"]').val();
            let question_name = $('.formdelitem input[name="question_name"]').val();
            let url = parent.configs.help_url;
            $.ajax({
                url: url+pk,
                //data: form.serialize(),
                type: "DELETE",
                headers: {'X-CSRFToken': getCookie('csrftoken') },
                success: function(){
                    $('#helper-body').find('[data-id_question="'+question_name+'"]').remove();
                    var label = $('label[for="'+question_name+'"]');
                    var icon = label.closest(".helpbtn").find('i');
                    icon.remove();
                    label.unwrap();
                    $("#del_modal_"+parent.instance).modal('hide');
                    parent.hide_palette();
                    parent.show_elements();
                },
                error: function(error){
                    console.log(error);
                }
            });
        }
    }
    add_element(data){
        let parent = this;
        var protohtml = $('#helper-prototype').html();
        let repl_list = [["$title", 'help_title'],
                        ["$text", 'help_text'],
                        ["$id_view", 'id_view'],
                        ["$id_question", 'question_name'],
                        ["$id_pk", 'id']
                        ];
        for( let key of repl_list){
            protohtml = protohtml.replace(key[0], data[key[1]] )
        }
        var byline = '';
        if (this.has_perm('djgentelella.change_help')){
            byline = '<button class="btn btn-xs btn-edit" ><i class="fa fa-edit blue"></i></button>';
        }
        if (this.has_perm('djgentelella.delete_help')){
            byline += '<button class="btn btn-xs btn-del" ><i class="fa fa-minus-circle red"></i></button>';
        }
        protohtml = protohtml.replace('$byline', byline)
        var instance = $(protohtml);
        instance.find('.btn-edit').on('click', this.show_edit_modal(this));
        instance.find('.btn-del').on('click', this.show_delete_modal(this));
        $('#helper-body').append(instance);
        this.add_label_icon(data);
        //console.log(protohtml);

    }
    has_perm(perm){
        let dev = false;
        if(this.configs.permissions.hasOwnProperty(perm)){
            dev = this.configs.permissions[perm];
        }

       return dev;
    }
    show_palette(){
        $("#content_"+this.instance).collapse('show');
    }

    show_edit_modal(parent){
      return  function(){
        var item = $(this).closest('.helperitem');
        let modal =$("#modal_"+parent.instance);
        modal.find('input[name="help_title"]').val(item.find(".title").html());
        modal.find('textarea[name="help_text"]').val(item.find(".excerpt").html());
        modal.find('input[name="pk"]').val(item.data('id-item'));
        modal.find('input[name="id_view"]').val(item.data('id_view'));
        modal.find('input[name="question_name"]').val(item.data('id_question'));
        modal.find('input[name="ftype"]').val("edit");
        $("#modal_"+parent.instance).modal('show');
      }
    }
    send_edit_data(parent){
        return function(){
            let modal = $(this).closest('.modal');
            let form = modal.find('form');
            let url = parent.configs.help_url;
            let verb = 'POST';
            let pk = form.find('input[name="pk"]').val();
            if(pk != ''){
                url = url+pk;
                verb = 'PUT';
            }

            $.ajax({
                url: url,
                data: form.serialize(),
                type: verb,
                headers: {'X-CSRFToken': getCookie('csrftoken') },
                success: function(result){
                    $('[data-id-item="'+result['id']+'"]').remove();
                    parent.add_element(result);
                    modal.modal('hide');
                },
                error: function(error){
                    console.log(error);
                }
            })
        }
    }
    add_start_label_icon(){
        let parent = this;
        if(!parent.add_tool_active){
            $(".right_col").find('label').each(function(i, e){
                let item = $(e);
                let forlabel = item.attr('for');
                if(item.parent().attr('class') != "helpbtn" && parent.has_perm('djgentelella.change_help')){
                    item.wrap('<div class="helpbtn" data-question_name="'+forlabel+'"></div>' );
                    let img = $('<i class="fa fa-question-circle help_i"></i>');
                    img.on('click', parent.show_help_in_box(parent, forlabel));
                    item.closest('.helpbtn').prepend(img);
                }
            });
        }else{
            var inotgreen = $(".helpbtn").find("i:not(.green)");
            var label = inotgreen.closest(".helpbtn").find('label');
            inotgreen.remove();
            label.unwrap();

        }
        }
    add_label_icon(data){
        let parent = this;
        let item = $('label[for="'+data.question_name+'"]');
        if(item.parent().attr('class') != "helpbtn"){
            item.wrap('<div class="helpbtn" data-question_name="'+data.question_name+'"></div>' );
            let img = $('<i class="fa fa-question-circle green help_i"></i>&nbsp;');
            img.on('click', this.show_help_in_box(this, data.question_name));
            item.closest('.helpbtn').prepend(img);
        }else{
            item.closest(".helpbtn").find('.help_i').addClass('green');
        }
    }
    show_help_in_box(parent, question_name){
        return function(){
            let qname = $('[data-id_question="'+question_name+'"]');
            if(qname.length>0){
                parent.hide_elements();
                qname.show();
                parent.show_palette();
            }else{
                let label = $('label[for="'+question_name+'"]');
                let modal =$("#modal_"+parent.instance);
                modal.find('input[name="help_title"]').val(label.text());
                modal.find('textarea[name="help_text"]').val("");
                modal.find('input[name="pk"]').val("");
                modal.find('input[name="id_view"]').val(parent.configs.id_view);
                modal.find('input[name="question_name"]').val(question_name);
                modal.find('input[name="ftype"]').val("add");
                $("#modal_"+parent.instance).modal('show');
            }
        }
    }
    add_commands_toolbar(){
        let parent = this;
        $("#show_help_"+this.instance).on('click', function(){
            parent.add_start_label_icon();
            parent.add_tool_active = !parent.add_tool_active;
            return false;
        });

 $("#expand_"+parent.instance).on('click', function(){
     let instance = $("#content_"+parent.instance);
     let iint = $("#expand_"+parent.instance+" i");

     $(".byline").toggle();
 });




    }
    show_delete_modal(parent){
        return function(){
            var item = $(this).closest('.helperitem');
            $('.formdelitem input[name="pk"]').val(item.data('id-item'));
            $('.formdelitem input[name="question_name"]').val(item.data('id_question'));

            $('.delp').html(item.find(".title").html());
            $("#del_modal_"+parent.instance).modal();

        }
    }
}

$.fn.helper_box = function($elemid){
     var helperbox = new HelperBox($elemid, this, document.help_widget);
     helperbox.get_help_list();
}


interact('.resize-drag')
  .resizable({
    // resize from all edges and corners
    edges: { left: true, right: true, bottom: true, top: true },

    listeners: {
      move (event) {
        var target = event.target
        var x = (parseFloat(target.getAttribute('data-x')) || 0)
        var y = (parseFloat(target.getAttribute('data-y')) || 0)

        // update the element's style
        target.style.width = event.rect.width + 'px'
        target.style.height = event.rect.height + 'px'

        $('#helper-body').css('height',(event.rect.height-50) + 'px');

        // translate when resizing from top or left edges
        x += event.deltaRect.left
        y += event.deltaRect.bottom

        target.style.webkitTransform = target.style.transform =
          'translate(' + x + 'px,' + y + 'px)'

        target.setAttribute('data-x', x)
        target.setAttribute('data-y', y)
      }
    },
    modifiers: [
      // keep the edges inside the parent
      interact.modifiers.restrictEdges({
        outer: 'parent'
      }),

      // minimum size
      interact.modifiers.restrictSize({
        min: { width: 150, height: 350 }
      })
    ],

    inertia: true
  })
  .draggable({
    listeners: { move: window.dragMoveListener },
    inertia: true,
    modifiers: [
      interact.modifiers.restrictRect({
        restriction: 'parent',
        endOnly: true
      })
    ]
  })

function build_select2_init(instance){
    var autocompleteselect2 = {
        'remote': [],
        'related': {}
    };
    instance.each(function(index, elem){

        let ins=$(this);
        let obj = {
            'id': "#"+ins.attr('id'),
            'url':  ins.data('url'),
            'start_empty': ins.data('start_empty')
        };
        let isrelated = ins.data('related');
        if (isrelated != undefined){
            obj['position'] = parseInt(ins.data('pos'));
            let groupname = ins.data('groupname');
            if (!autocompleteselect2['related'].hasOwnProperty(groupname)){
                autocompleteselect2['related'][groupname]=[];
            }
            autocompleteselect2['related'][groupname].push(obj);
        }else{
            autocompleteselect2['remote'].push(obj);
        }
    })
    $(window).select2related('remote', autocompleteselect2['remote']);
    $.each(autocompleteselect2['related'], function(index, value) {
        function compare(a, b) {
          if (a.position > b.position) return 1;
          if (b.position > a.position) return -1;
          return 0;
        }
        $(window).select2related('related', value.sort(compare));
    });
}



function decore_select2 (data) {
    // We only really care if there is an element to pull classes from
    if (!data.element) {
      return data.text;
    }
    var $element = $(data.element);
    var $wrapper = $('<span></span>');
    $wrapper.addClass($element[0].className);
    $wrapper.text(data.text);
    return $wrapper;
}

function decore_img_select2 (data) {
  if(!data.url && data.text){
      return $('<span>'+data.text+'</span>');
  }
  if (!data.url) {
    return "";
  }
  let img_width = "2em";   let img_height="2em;";
  if(data.img_width != undefined){img_width=data.img_width;}
  if(data.img_height != undefined){ img_height=data.img_height; }
  var $state = $('<span><img style="width: '+img_width+'; height: '+img_height+';" src="' + data.url+ '" class="img-flag" /> ' +  data.text + '</span>');
  return $state;
};


function load_date_range(instance, format='DD/MM/YYYY') {
    var options = {
        'autoUpdateInput': false,
         'locale': {
            format: format,
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options["startDate"] =  days[0];
        options["endDate"] = days[1];
    }
    return options;
}

function load_datetime_range(instance, format='DD/MM/YYYY HH:mm A') {
    var options = {
        'timePicker': true,
        'timePicker24Hour': true,
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: format
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            'timePicker': true,
            'timePicker24Hour': true,
            'startDate': days[0],
            'endDate': days[1],
            'locale': {
                format: format
            }
        }
    }
    return options;
}

function load_date_range_custom(instance, format='DD/MM/YYYY') {
    var options = {
        startDate: moment().startOf('hour'),
        endDate: moment().startOf('hour').add(32, 'hour'),
        ranges: {
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Next Week': [moment(), moment().add(7, 'days')],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        locale: {
            format: format,
        }
    }
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'ranges': {
                'Last 7 Days': [moment(days[0], format).subtract(6, 'days'), moment(days[0], format)],
                'Next Week': [moment(days[0], format), moment(days[0], format).add(7, 'days')],
                'Last 30 Days': [moment(days[0], format).subtract(29, 'days'), moment(days[0], format)],
                'This Month': [moment(days[0], format).startOf('month'), moment(days[0], format).endOf('month')],
                'Last Month': [moment(days[0], format).subtract(1, 'month').startOf('month'), moment(days[0], format).subtract(1, 'month').endOf('month')]
            },
            'locale': {
                format: format,
            }
        }
    }
    return options;
}

function grid_slider(instance) {
    let obj = $(instance[0]);

    let to = obj.attr('data-from_max');

    let from = obj.attr('data-from_min');

    if ($("input[name=" + obj.attr('data-target-to') + "]").val() > 200) {
        to = $("input[name=" + obj.attr('data-target-to') + "]").val()
    }

    if ($("input[name=" + obj.attr('data-target-from') + "]").val() > 200) {
        from = $("input[name=" + obj.attr('data-target-from') + "]").val()
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'to': to,
        'type': 'double',
        'step': obj.attr('data-step'),
        'prefix': obj.attr('data-prefix'),
        'from_fixed': obj.attr('data-from_fixed') === 'true',
        'to_fixed': obj.attr('data-to_fixed') === 'true',
        'to_max': obj.attr('data-to_max'),
        'hide_min_max': obj.attr('data-hide_min_max'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target-from') + "]").val(data.from);
            $("input[name=" + obj.attr('data-target-to') + "]").val(data.to);
        }
    }
    return option;
}
function grid_slider_single(instance) {
    let obj = $(instance[0]);


    let from = obj.attr('data_from');

    if ($("input[name=" + obj.attr('data-target') + "]").val() > 0) {
        from = $("input[name=" + obj.attr('data-target') + "]").val()
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'type': 'single',
        'prefix': obj.attr('data-prefix'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target') + "]").val(data.from);
        }
    }
    return option;
}
function date_grid_slider(instance) {

    let obj = $(instance);
    let input = $("input[name=" + obj.attr('data-target') + "]").val();

    function dateToTS(date) {
        return date.valueOf();
    }

    function tsToDate(ts) {
        var lang = "en-US";
        var d = new Date(ts);

        return d.toLocaleDateString(lang, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            hour12: false,


        });
    }

    return instance.ionRangeSlider({
        type: "single",
        hide_min_max: false,
        min: dateToTS(new Date(obj.attr('data_min'))),
        max: dateToTS(new Date(obj.attr('data_max'))),
        from: dateToTS(new Date(input != undefined ? input : obj.attr('data_from'))),
        prettify: tsToDate,
        onChange: function (data) {
            var day = new Date(data.from);
            day = day.getFullYear() + "-" + (day.getMonth() + 1) + "-" + day.getDate() + " " + day.getHours() + ":" + day.getMinutes()
            $("input[name=" + obj.attr('data-target') + "]").val(day);
        }
    })
}


function create_identifiers(items){
     var descriptors=[];
     for(var x=0; x<items.length; x++){
        if(items[x].charAt(0) == '#' || items[x].charAt(0) == '.' ){
            descriptors.push(items[x]);
        }else{
            descriptors.push('input[name="'+items[x]+'"],textarea[name="'+items[x]+'"],select[name="'+items[x]+'"]');
        }
     }
     return descriptors;
}

function showHideRelatedFormFields(instance){
    var rel = instance.data('rel');
    var parentclass = instance.data('shparent');
    if(parentclass == undefined) parentclass = '.row'
    if(rel != undefined ){
        var relateditems = create_identifiers(instance.data('rel').split(';'));
        instance.on('change', function(){
            for(var x=0; x<relateditems.length; x++){
                if(this.checked){
                    $(relateditems[x]).closest(parentclass).show();
                }else{
                    $(relateditems[x]).closest(parentclass).hide();
                }
            }
        });
        instance.trigger('change');
    }
    var relh = instance.data('relhidden');
    if(relh != undefined ){
        var relateditemsh = create_identifiers(relh.split(';'));
        instance.on('change', function(e){
            for(var x=0; x<relateditemsh.length; x++){
                if(this.checked){
                    $(relateditemsh[x]).closest(parentclass).hide();
                }else{
                    $(relateditemsh[x]).closest(parentclass).show();
                }
            }
        });
         instance.trigger('change');
    }
}


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

function build_gigapixel_storymap(instance) {
    instance.each(function(index, element) {
        var instanceid = document.getElementById(element.id).id;
        var data_url = element.getAttribute('data-url');
        var storymap_options = element.getAttribute('storymap_options');

        var storymap = new VCO.StoryMap(instanceid, data_url, storymap_options);

        var e = $(window).height(),
        t = $(`#${instanceid}`);
        t.height(e - 20);

        $(window).resize(function() {
            e = $(window).height();
            t.height(e - 20);
            storymap.updateDisplay();
        });
    })
}

function build_mapbased_storymap(instance) {
    instance.each(function(index, element) {
        var instanceid = document.getElementById(element.id).id;
        var data_url = element.getAttribute('data-url');

        var storymap = new KLStoryMap.StoryMap(instanceid, data_url);

        var e = $(window).height(),
        t = $(`#${instanceid}`);
        t.height(e - 20);

        $(window).resize(function() {
            e = $(window).height();
            t.height(e - 20);
            storymap.updateDisplay();
        });
    })
}

function build_storyline(instance){
        instance.each(function (index, element) {
            var instance_element = element.id;
            if (element.attributes['width'] != undefined){
                var widget_width = element.attributes['width'].value;
            }else{
                var widget_width = element.parentNode.offsetWidth-100;
            }

            url = element.attributes['data-url'].value;
            $.ajax({
                method: "GET",
                url: url,
                dataType: "json",
                error: function(e) {
                    $(element).html('<div>'+e.responseText+'</div>');
                },
            }).done(function(msg){
                window.storyline = new Storyline(instance_element, msg);
                window.storyline.resetWidth(widget_width, 'scroll');
            });
        });
}


function build_calendar(instance){
    instance.each(function (index, element) {
            var calendarEl = document.getElementById(element.id);
            var element_name = element.getAttribute('name')
            var widget_name = element_name.substring(0, element_name.length-8);
            events = window['events' + widget_name];
            calendar_options = window['calendar_options' + widget_name];
            calendar_options.events = events;
            var calendar = new FullCalendar.Calendar(calendarEl, calendar_options);
            calendar.render();
            $(element).closest("form").on("submit", function (event) {
                $(`#${widget_name}_events-input-src`).val(JSON.stringify(calendar.getEvents()));
            });
        });
}

function build_timeline(instances){
    instances.each(function (index, element) {
        var instanceid = element.id;
        var instance = $(element);
        var dataoptions = instance.data();
        var keys = Object.keys(dataoptions);
        var options = {}
        for (var x=0; x<keys.length; x++){
            if(keys[x].startsWith('option_')){
                 options[keys[x].replace('option_', '')] = dataoptions[keys[x]]
            }
        }
        timeline = new TL.Timeline(instanceid, instance.data('url'), options);
        window.addEventListener('resize', function() {
            var embed = document.getElementById(instanceid);
            embed.style.height = getComputedStyle(document.body).height;
            timeline.updateDisplay();
        })
    });
}

function show_errors_media_record(error){
    Swal.fire({
          icon: 'error',
          title: gettext('Sorry, there is a problem'),
          text: gettext('Media device is not available'),
        })
}
function getPhotoRecord(element){
    let id = element.id
    let media = {
          tag: 'video',
          type: 'image/png',
          ext: '.png',
          gUM: {video: true}
    }

    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        video: $("#"+id+"_video"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        width: $("#"+id).data('width') || '320px',
        height: $("#"+id).data('height') || '240px',
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            this.canvas.hide();
            this.video.hide();
            this.canvas[0].style.width=this.width;
            this.canvas[0].style.height=this.height;
            this.video[0].style.width=this.width;
            this.video[0].style.height=this.height;
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var video = this.video[0];
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                     video.srcObject = _stream;
                     parent.tracks = _stream.getTracks();
                }).catch(show_errors_media_record);
                this.video.show();
                this.canvas.hide();
            }else if(this.status==1){
                let canvas = this.canvas[0];
                this.video.hide();
                canvas.getContext('2d').drawImage(this.video[0], 0, 0, canvas.width, canvas.height);
                this.canvas.show();
            }else{
                this.status = -1;
                this.save_media();
                if(this.tracks) this.tracks.forEach(track => track.stop());
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text(gettext('Start'));
            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                    $("#"+this.id+"_btn i").attr('class', 'fa fa-camera');
                    $("#"+this.id+"_btn span").text(gettext(gettext('Capture')));
            }
            if(this.status==2) {
                    $("#"+this.id+"_btn i").attr('class', 'fa fa-check');
                    $("#"+this.id+"_btn span").text(gettext('Save'));
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null) this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.canvas.hide();
            this.video.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            var parent = this;
            this.canvas[0].toBlob((blob) => {
              let file = new File([blob], "photo"+parent.media.ext, { type: parent.media.type  })
              let container = new DataTransfer();
              container.items.add(file);
            $("#"+parent.id)[0].files = container.files;
            }, parent.media.type);
        }
    }

    v.initialize()
    return v;
}


function getVideoRecord(element){
    let id = element.id
    let media = {
                  tag: 'video',
                  type: 'video/webm',
                  ext: '.mp4',
                  gUM: {video: true, audio: true}
                }
    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        video: $("#"+id+"_video"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        width: $("#"+id).data('width') || '320px',
        height: $("#"+id).data('height') || '240px',
        chunks: [],
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            this.video[0].style.width=this.width;
            this.video[0].style.height=this.height;
            this.video.hide();
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var video = this.video[0];
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                    video.srcObject = _stream;
                    parent.tracks = _stream.getTracks();
                    parent.recorder = new MediaRecorder(_stream);
                    parent.recorder.ondataavailable = e => {
                    parent.chunks.push(e.data);
                    if(parent.recorder.state == 'inactive')  parent.save_media();
                    };
                }).catch(show_errors_media_record);
                this.video.show();

            }else if(this.status==1){
                this.chunks=[];
                if(this.recorder) this.recorder.start();
            }else{
                if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
                this.cancel(true)
                this.status = -1;
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text(gettext('Start'));

            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                $("#"+this.id+"_btn i").attr('class', 'fa fa-play');
                $("#"+this.id+"_btn span").text(gettext('Record'));
                $("#"+this.id+"_container .mediareproductor").remove();
            }
            if(this.status==2) {
                $("#"+this.id+"_btn i").attr('class', 'fa fa-pause');
                $("#"+this.id+"_btn span").text(gettext('Recording...'));
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null && this.recorder.state != 'inactive') this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.video.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            let file = new File(this.chunks, "record"+this.media.ext, {type: this.media.type , lastModified:new Date().getTime()});
            let container = new DataTransfer();
            container.items.add(file);
            $("#"+this.id)[0].files = container.files;
             let blob = new Blob(this.chunks, {type: this.media.type })
             let url = URL.createObjectURL(blob)
             mt = document.createElement(this.media.tag)
             mt.controls = true;
             mt.src = url;
             mt.className = "mediareproductor"
             mt.style.width=this.width;
             mt.style.height=this.height;
             $("#"+this.id+"_container").append(mt);
        }
    }

    v.initialize()
    return v;
}


function getAudioRecord(element){
    let id = element.id
    let media = {
                  tag: 'audio',
                  type: 'audio/ogg',
                  ext: '.ogg',
                  gUM: {video: false, audio: true}
                }
    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        chunks: [],
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                    parent.tracks = _stream.getTracks();
                    parent.recorder = new MediaRecorder(_stream);
                    parent.recorder.ondataavailable = e => {
                    parent.chunks.push(e.data);
                    if(parent.recorder.state == 'inactive')  parent.save_media();
                    };
                }).catch(show_errors_media_record);
            }else if(this.status==1){
                this.chunks=[];
                if(this.recorder) this.recorder.start();
            }else{
                if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
                this.cancel(true)
                this.status = -1;
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text(gettext('Start'));
                $("#"+this.id+"_container .mediareproductor").remove();
            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                $("#"+this.id+"_btn i").attr('class', 'fa fa-play');
                $("#"+this.id+"_btn span").text(gettext('Record'));
            }
            if(this.status==2) {
                $("#"+this.id+"_btn i").attr('class', 'fa fa-pause');
                $("#"+this.id+"_btn span").text(gettext('Recording...'));
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            let file = new File(this.chunks, "record"+this.media.ext, {type: this.media.type , lastModified:new Date().getTime()});
            let container = new DataTransfer();
            container.items.add(file);
            $("#"+this.id)[0].files = container.files;
             let blob = new Blob(this.chunks, {type: this.media.type })
             let url = URL.createObjectURL(blob)
             mt = document.createElement(this.media.tag)
             mt.controls = true;
             mt.src = url;
             mt.className = "mediareproductor"
             $("#"+this.id+"_container").append(mt);
        }
    }

    v.initialize()
    return v;
}



function getMediaRecord(element, mediatype){
    if(mediatype=='photo'){
        return getPhotoRecord(element);
    }
    if(mediatype=='video'){
        return getVideoRecord(element);
    }
    if(mediatype === "audio"){
        return getAudioRecord(element)
    }
}


///////////////////////////////////////////////
//  Init widgets digital signature
///////////////////////////////////////////////
var socket_connections = {};
var socket_manager_instances = {};
const max_close_inicialice = 5;
var count_close_inicialice = 0;

// Configuración del MutationObserver
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'data-port') {
            let port = mutation.target.getAttribute('data-port');
            mutation.target.setAttribute("href",
                "firmador:" + window.location.protocol + "//" + window.location.host + "#" + port);
        }
    });
});

build_cors_headers = function (instance) {
    let port = instance.getAttribute('data-port');
    instance.setAttribute("href", "firmador:" + window.location.protocol + "//" + window.location.host + "#" + port);
    observer.observe(instance, {attributes: true});
}

build_ws_url = function (base) {
    return base;
}

build_digital_signature = function (instance) {

    const widgetId = instance.getAttribute("id");
    const url_ws = build_ws_url(instance.getAttribute("data-ws-url"));
    const container = instance.closest(".widget-digital-signature");
    const container_tag = `container-${widgetId}`;
    const doc_instance = {
        "pk": instance.getAttribute("data-pk"),
        "cc": instance.getAttribute("data-cc"),
        "value": instance.getAttribute("data-value")
    }
    const urls = {
        "logo": instance.getAttribute("data-logo"),
        "sign_doc": instance.getAttribute("data-renderurl"),
        "renderattr": instance.getAttribute("data-renderattr")
    }
    container.setAttribute("data-widget-id", container_tag);

    // pdfviewer
    const defaultPage = instance.getAttribute("data-default-page") || "first";

    // Create a new instance of the PDF viewer with the appropriate settings
    const pdfInstance = new PdfSignatureComponent(container, defaultPage, urls, doc_instance);

    if (!doc_instance) {
        console.error("You must define the doc_instance variable.");
        return;
    }

    //Custom Event
    const event = new CustomEvent("document:signed", {
        bubbles: true,  // Important for global handlers
        detail: {
            message: "Signed document",
            instance: doc_instance,
        }
    });

    // Signature
    let signatureManager = new SignatureManager(widgetId, container, url_ws, pdfInstance, event);
    signatureManager.startSign(doc_instance, urls['logo']);

    // Store the instance in a global object with key per widget ID
    if (!window.pdfSignatureComponents) {
        window.pdfSignatureComponents = {};
    }

    // Add the instance to the global object if it does not exist
    if (!window.pdfSignatureComponents[container_tag]) {
        window.pdfSignatureComponents[container_tag] = pdfInstance;
    }


}

///////////////////////////////////////////////
//  PDF preview Digtal Signature
///////////////////////////////////////////////
class PdfSignatureComponent {
    constructor(container, defaultPage, urls, doc_instance) {
        this.container = container;
        this.defaultPage = defaultPage;
        this.widgetId = container.getAttribute("data-widget-id");
        this.urls = urls;
        this.doc_instance = doc_instance;

        // Internal elements
        this.signature = container.querySelector('.signature');
        this.canvas = container.querySelector('.pdfviewer');
        this.btn_prev = container.querySelector('.prev');
        this.btn_next = container.querySelector('.next');
        this.page_num = container.querySelector('.page_num');
        this.page_number = container.querySelector('.page_number');
        this.page_count = container.querySelector('.page_count');
        this.sub_canvas_container = container.querySelector('.sub_canvas_container');

        // Verify that all required elements are present
        if (!this.signature || !this.canvas || !this.btn_prev || !this.btn_next || !this.page_num || !this.page_number || !this.page_count || !this.sub_canvas_container) {
            console.warn("Falta alguno de los elementos requeridos en este componente. Se omite su inicialización.");
            return;
        }

        // Variables specific to the component
        this.pdfDoc = null;
        this.pageNum = 1;
        this.pageRendering = false;
        this.pageNumPending = null;
        this.scale = 1.2;
        this.signX = 0;
        this.signY = 198;
        this.signWidth = 133;
        this.signHeight = 133;

        // Initializes the processes
        this.initEvents();
        this.initPDFViewer();
        this.initInteract();
        this.initSignatureSettings();

    }

    initEvents() {
        this.btn_prev.addEventListener('click', () => this.onPrevPage());
        this.btn_next.addEventListener('click', () => this.onNextPage());
        this.page_number.addEventListener('change', (e) => this.renderPage(e.target.value));
        this.page_number.addEventListener('keyup', (e) => this.renderPage(e.target.value));
    }

    initPDFViewer() {

        if (typeof this.urls['sign_doc'] === 'undefined') {
            console.warn("The variable 'sign_doc' is not defined.");
            return;
        }
        pdfjsLib.getDocument(this.urls['sign_doc'] + "?" + this.urls['renderattr']).promise.then((pdfDoc_) => {
            this.pdfDoc = pdfDoc_;
            this.page_count.textContent = pdfDoc_.numPages;

            // define page number
            if (this.defaultPage === "last") {
                this.pageNum = this.pdfDoc.numPages;
            } else if (this.defaultPage === "first") {
                this.pageNum = 1;
            } else {
                let numPage = parseInt(this.defaultPage, 10);
                if (!isNaN(numPage) && numPage > 0 && numPage <= this.pdfDoc.numPages) {
                    this.pageNum = numPage;
                } else {
                    console.warn("Invalid page number, starting on the first page.");
                    this.pageNum = 1;
                }
            }


            this.renderPage(this.pageNum);
        });
    }

    onPrevPage() {
        if (this.pageNum <= 1) return;
        this.pageNum--;
        this.queueRenderPage(this.pageNum);
    }

    onNextPage() {
        if (this.pageNum >= this.pdfDoc.numPages) return;
        this.pageNum++;
        this.queueRenderPage(this.pageNum);
    }

    queueRenderPage(num) {
        if (this.pageRendering) {
            this.pageNumPending = num;
        } else {
            this.renderPage(num);
        }
    }

    renderPage(num) {
        this.pageRendering = true;
        this.pdfDoc.getPage(num).then((page) => {
            const viewport = page.getViewport({scale: this.scale});
            this.canvas.height = viewport.height;
            this.canvas.width = viewport.width;

            const renderContext = {
                canvasContext: this.canvas.getContext('2d'), viewport: viewport
            };
            const renderTask = page.render(renderContext);

            renderTask.promise.then(() => {
                this.pageRendering = false;
                if (this.pageNumPending !== null) {
                    this.renderPage(this.pageNumPending);
                    this.pageNumPending = null;
                }
            });
        });
        this.page_num.textContent = num;
        this.page_number.value = num;
    }

    initInteract() {
        // First instance of draggable and resizable with interact.js
        interact(this.signature)
            .draggable({
                inertia: true, modifiers: [interact.modifiers.restrictRect({
                    restriction: this.canvas, endOnly: false
                })], autoScroll: true, listeners: {
                    move: (event) => this.dragMoveListener(event)
                }
            })
            .resizable({
                edges: {left: true, right: true, bottom: true, top: true}, listeners: {
                    move: (event) => {
                        let target = event.target;
                        let x = (parseFloat(target.getAttribute('data-x')) || 0);
                        let y = (parseFloat(target.getAttribute('data-y')) || 0);

                        target.style.width = event.rect.width + 'px';
                        target.style.height = event.rect.height + 'px';

                        x += event.deltaRect.left;
                        y += event.deltaRect.top;

                        target.style.transform = `translate(${x}px, ${y}px)`;
                        target.setAttribute('data-x', x);
                        target.setAttribute('data-y', y);
                        target.textContent = Math.round(event.rect.width) + '\u00D7' + Math.round(event.rect.height);

                        this.signWidth = event.rect.width;
                        this.signHeight = event.rect.height;
                        this.signX = x;
                        this.signY = y;
                    }
                }, modifiers: [interact.modifiers.restrictEdges({outer: 'parent'}), interact.modifiers.restrictSize({
                    min: {
                        width: 100, height: 50
                    }
                })], inertia: true
            });

        // Second instance of draggable with autoScroll over the container
        interact(this.signature)
            .draggable({
                inertia: true, modifiers: [interact.modifiers.restrictRect({
                    restriction: this.canvas, endOnly: false
                })], autoScroll: {
                    container: this.sub_canvas_container, margin: 50, distance: 5, interval: 50
                }, listeners: {
                    move: (event) => this.dragMoveListener(event)
                }
            });

        this.canvas.addEventListener('dblclick', (event) => this.moveSignatureToClick(event));
    }

    moveSignatureToClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        const signatureWidth = this.signature.offsetWidth;
        const signatureHeight = this.signature.offsetHeight;

        const centerX = x - signatureWidth / 2;
        const centerY = y - signatureHeight / 2;

        this.updatePosition(this.signature, centerX, centerY);
    }


    dragMoveListener(event) {
        const target = event.target;
        const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
        const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
        this.updatePosition(target, x, y);
    }

    updatePosition(target, x, y) {
        target.style.transform = `translate(${x}px, ${y}px)`;
        const {x: xAdjusted, y: yAdjusted} = this.adjustPositionToFitWithinCanvas(target, x, y);
        target.style.transform = `translate(${xAdjusted}px, ${yAdjusted}px)`;
        target.setAttribute('data-x', xAdjusted);
        target.setAttribute('data-y', yAdjusted);
        this.signX = Math.round(xAdjusted);
        this.signY = Math.round(yAdjusted);
    }

    adjustPositionToFitWithinCanvas(target, x, y) {
        const canvasRect = this.canvas.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        if (targetRect.right > canvasRect.right) {
            x -= targetRect.right - canvasRect.right;
        }
        if (targetRect.bottom > canvasRect.bottom) {
            y -= targetRect.bottom - canvasRect.bottom;
        }
        return {x, y};
    }

    initSignatureSettings() {
        // A base configuration is applied by cloning the signature element
        const tempSignature = this.signature.cloneNode(true);
        tempSignature.style = '';
        tempSignature.classList.remove("right", "left", "top", "bottom", "full", "none");
        tempSignature.style.visibility = 'visible';
        tempSignature.style.width = 'auto';
        tempSignature.style.height = 'auto';
        tempSignature.style.overflow = 'visible';
        const textElem = tempSignature.querySelector('.text');
        if (textElem) textElem.style.wordBreak = 'break-word';

        this.formatAndLoadContent(tempSignature)
            .then(() => {
                this.signature.className = tempSignature.className;
                this.signature.style.cssText = tempSignature.style.cssText;
                this.signature.innerHTML = tempSignature.innerHTML;
                this.updatePosition(this.signature, 198, 0);
            })
            .catch(error => {
                console.error(gettext("Error when applying setting to signature: "), error);
            });
    }

    async formatAndLoadContent(element, content) {
        const imageContainer = element.querySelector('.image');
        const textContainer = element.querySelector('.text');
        if (imageContainer) imageContainer.innerHTML = '';
        if (textContainer) textContainer.innerHTML = '';
        try {
            // Here you can load the image or update the text of the signature
            // await this.loadSignatureImage(signatureImageURL, imageContainer);
        } catch (error) {
            console.error(gettext("Error loading content: "), error);
        }
    }

    async createTemporarySignature(content) {
        let tempSignature = window.app.signature.cloneNode(true);
        tempSignature.id = 'temp_signature';
        tempSignature.style.position = 'absolute';
        tempSignature.style.visibility = 'hidden';
        let textElem = tempSignature.querySelector('.text');
        if (textElem) textElem.style.wordBreak = 'break-word';
        this.sub_canvas_container.appendChild(tempSignature);
        await this.formatAndLoadContent(tempSignature, content);
        return tempSignature;
    }

    // If required, you can define a method for loading an image
    loadSignatureImage(signatureImage, imageContainer) {
        return new Promise((resolve, reject) => {
            if (!signatureImage) {
                resolve();
                return;
            }
            const img = new Image();
            img.src = signatureImage;
            img.alt = 'signature-image';
            img.onload = () => {
                if (imageContainer) imageContainer.appendChild(img);
                resolve();
            };
            img.onerror = () => {
                reject(new Error(gettext("Error loading image")));
            };
        });
    }

    getDocumentSettings() {
        const displayScale = this.canvas.getBoundingClientRect().width / this.canvas.width;
        const xReal = this.signX / displayScale;
        const yReal = this.signY / displayScale;
        const wReal = this.signWidth / displayScale;
        const hReal = this.signHeight / displayScale;

        const xPdf = xReal / this.scale;
        const yPdf = yReal / this.scale;
        const wPdf = wReal / this.scale;
        const hPdf = hReal / this.scale;

        return {
            pageNumber: this.pageNum,
            signWidth: Math.round(wPdf),
            signHeight: Math.round(hPdf),
            signX: Math.round(xPdf),
            signY: Math.round(yPdf),
        };
    }
}

///////////////////////////////////////////////
//  Signature manager Digital Signature
///////////////////////////////////////////////
class SignatureManager {
    constructor(input_id, container, url_ws, pdfvisor, custom_event) {
        this.input_id = input_id;
        this.container = container;
        this.modal = new bootstrap.Modal(container.querySelector("#loading_sign"));
        this.firmador = new DocumentClient(container, container.getAttribute("data-widget-id"), this, url_ws, custom_event, this.doc_instance);
        this.signerBtn = container.querySelector(".btn_signer");
        this.errorsContainer = container.querySelector(".errors_signer");
        this.refreshBtn = container.querySelector(".btn_signer_refresh");
        this.socketError = false;
        this.pdfvisor = pdfvisor;

        this.initEvents();
    }

    initEvents() {
        if (this.signerBtn) {
            this.signerBtn.addEventListener('click', () => this.sign());
        }
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.refresh());
        }
    }

    startSign(doc_instance, logo_url = null) {
        if (this.socketError) {
            alertSimple(errorInterpreter(3), gettext("Error"), "error");
            return;
        }

        this.doc_instance = doc_instance;
        this.logo_url = logo_url;

        this.clearErrors();

        this.firmador.start_sign(doc_instance, logo_url)
    }

    refresh() {
        this.socketError = false;
        this.firmador.remotesigner.inicialize();

        this.clearErrors();
        this.firmador.start_sign(this.doc_instance, this.logo_url);
    }

    sign() {
        this.clearErrors();
        this.firmador.do_sign_remote();
    }

    addError(errorCode) {
        let title = document.createElement('p');
        title.classList.add('mt-2', 'text-danger', 'mb-0');
        title.innerHTML = `<i class="fa fa-times-circle" aria-hidden="true"></i> <span class="fw-bold"> ${gettext("Errors")} </span>`;
        let errorElement = document.createElement('p');
        errorElement.classList.add('text-danger', 'mx-3', 'small');
        errorElement.innerHTML = errorInterpreter(errorCode);
        this.errorsContainer.appendChild(title);
        this.errorsContainer.appendChild(errorElement);
    }

    clearErrors() {
        this.errorsContainer.innerHTML = '';
    }

    reloadPage() {
        window.location.reload();
    }

    showLoading() {
        this.modal.show();
    }

    hideLoading() {
        setTimeout(() => {
            this.modal.hide();
        }, 500);
    }
}

///////////////////////////////////////////////
//   Socket Digital Signature
///////////////////////////////////////////////
function responseManageTypeData(instance, err_json_fn, error_text_fn) {
    return function (response) {
        const contentType = response.headers.get("content-type");
        if (response.ok) {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            } else {
                return response.text();
            }
        } else {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                response.json().then(data => err_json_fn(data));
            } else {
                if (response.status === 406) {
                    // cierre de ventana para ingresar el PIN
                    error_text_fn(errorInterpreter(4));
                } else {
                    response.text().then(data => error_text_fn(data));
                }
            }
        }
        return Promise.reject(response);
    }
}

class SocketManager {
    constructor(url, signatureManager, instance) {
        this.url = url;
        this.signatureManager = signatureManager;
        this.instance = instance;

        this.connect();
    }

    connect() {
        socket_manager_instances[this.instance.socket_id] = this.instance;
        if (!socket_connections.hasOwnProperty(this.url)) {
            let ws = new WebSocket(this.url);
            ws.onerror = this.fn_error(this);
            ws.onclose = this.fn_close(this);
            ws.onopen = this.fn_open(this);
            ws.onmessage = this.fn_messages(this);
            socket_connections[this.url] = ws;
        }
    }

    fn_error(element) {
        return (event) => {
            // console.error("WebSocket error");
            element.signatureManager.hideLoading();
            alertSimple(errorInterpreter(3), gettext("Error"), "error");
            element.signatureManager.socketError = true;
        }
    }

    fn_close(element) {
        return (event) => {
            console.warn("WebSocket cerrado " + event.type);
            Reflect.deleteProperty(socket_connections, event.currentTarget.url);
            if (count_close_inicialice < max_close_inicialice) {
                count_close_inicialice += 1;
                element.instance.inicialize();
            }
        };
    }

    fn_open(element) {
        return (event) => {
            //       console.log("WebSocket conectado");
            element.signatureManager.socket_error = false;
            count_close_inicialice = 0;
        };
    }

    fn_messages(element) {
        return (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.hasOwnProperty("socket_id") && socket_manager_instances.hasOwnProperty(data["socket_id"])) {
                    socket_manager_instances[data["socket_id"]].receive_json(data);
                } else {
                    console.error("Socket id not found");
                }
            } catch (err) {
                console.error("Error al parsear mensaje WS:", err);
            }
        };
    }

    send(str) {
        if (!socket_connections.hasOwnProperty(this.url)) {
            this.connect();
        } else {
            if (socket_connections[this.url].readyState != WebSocket.OPEN) {
                Reflect.deleteProperty(socket_connections, this.url);
                this.connect();
            }
        }
        if (socket_connections.hasOwnProperty(this.url)) {
            socket_connections[this.url].send(str);
        }
    }
}

function callFetch(instance) {
    fetch(instance.url, {
        method: instance.type,
        body: instance.data,
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        },
        cache: 'no-cache', // do not use cache
    }).then(responseManageTypeData(instance, instance.error_json, instance.error_text))
        .then(data => instance.success(data))
        .catch(error => {
            instance.error(error);
        });
}

function FirmadorLibreLocal(docmanager, signatureManager) {
    return {
        "cert_url": "http://localhost:3516/certificates",
        "sign_url": "http://localhost:3516/sign",
        "success_get_certificates": function (data) {
            docmanager.success_certificates(data);
        },
        "get_certificates": function () {
            let parent = this;

            const instance = {
                url: this.cert_url,
                type: 'GET',
                data: null,
                success: function (data) {
                    parent.success_get_certificates(data);
                },
                error_text: function (message) {
                    // console.log(message);
                },
                error_json: function (error) {
                    // console.log(error);
                },
                error: function (error) {
                    // Unrecognized Firmador Libre
                    if (String(error) === "TypeError: NetworkError when attempting to fetch resource.") {
                        signatureManager.addError(1);
                    }
                }
            }
            callFetch(instance);
        },
        "sign": function (data) {
            if (data.hasOwnProperty("socket_id")) {
                Reflect.deleteProperty(data, "socket_id");
            }
            let json = JSON.stringify(data);
            let manager = docmanager;

            const fetch_instance = {
                'url': this.sign_url,
                'type': 'POST',
                'data': json,
                "success": function (data) {
                    // if the result is different from a string, it is possible that there is an error.
                    // console.log(data)
                    if (typeof data !== 'string') { //prevent option call
                        manager.local_done(data);
                    }

                },
                "error": function (error) {
                    // console.log(error);
                    signatureManager.hideLoading();
                    if (typeof error === "object") {
                        // close window for PIN entry
                        if (error.status === 406 && error.statusText === "Not Acceptable") {
                            alertSimple(errorInterpreter(4), gettext("Warning"), "warning");
                        }
                    }
                },
                "error_text": function (message) {
                    console.error("error_text", message);
                    signatureManager.hideLoading();
                },
                "error_json": function (error) {
                    console.error("error_json", error);
                    signatureManager.hideLoading();
                },
            };

            callFetch(fetch_instance);
        }
    }
}

const generateRandomString = () => {
    return Math.floor(Math.random() * Date.now()).toString(36);
};

function FirmadorLibreWS(docmanager, url, signatureManager) {
    var firmador = {
        "url": url,
        "websocket": null,
        "firmador_url": "http://localhost:3516",
        "socket_id": generateRandomString(),
        "receive_json": function (data) {
            // validate socket errors
            if (data.result === false && data.error) {
                signatureManager.hideLoading();
                if (typeof data.details === "string") {
                    // connection issues with the Firmador Libre API
                    if (data.details.includes("Connection refused")) {
                        signatureManager.addError(3);
                    } else {
                        alertSimple(errorInterpreter(999), gettext("Error"), "error");
                    }

                } else if (data.code) {
                    switch (data.code) {
                        case 0:
                            // when an unknown error occurs on the server
                            alertSimple(errorInterpreter(0), gettext("Error"), "error");
                            break;
                        case 6:
                            // when the new signature field position overlaps with an existing signature
                            alertSimple(errorInterpreter(6), gettext("Error"), "error");
                            break;
                        case 7:
                            // when the signature field is outside the page boundaries
                            alertSimple(errorInterpreter(7), gettext("Error"), "error");
                            break;
                        case 8:
                            // when an error occurs due to an incompatible library
                            alertSimple(errorInterpreter(8), gettext("Error"), "error");
                            break;
                        case 9:
                            // when an error occurs due to an unavailable cryptographic provider
                            alertSimple(errorInterpreter(9), gettext("Error"), "error");
                            break;
                        case 10:
                            // when an error occurs due to the signing algorithm
                            alertSimple(errorInterpreter(10), gettext("Error"), "error");
                            break;
                        case 11:
                            // when there are errors serializing data
                            alertSimple(errorInterpreter(11), gettext("Error"), "error");
                            break;
                        case 12:
                            // when an error occurs due to a signing service timeout
                            alertSimple(errorInterpreter(12), gettext("Error"), "error");
                            break;
                            // when an unknown error occurs
                            alertSimple(errorInterpreter(999), gettext("Error"), "error");
                            break;
                    }
                }
            } else {

                if (data.hasOwnProperty('report')) {
                    docmanager.validate_document_remote_done(data['report']);
                } else if (data.hasOwnProperty('tobesigned')) {
                    docmanager.do_sign_local(data);
                } else {
                    docmanager.remote_done(data)
                }

            }
        },

        "inicialize": function () {
            this.websocket = new SocketManager(url, signatureManager, this);

        },
        "local_done": function (data) {
            // console.log("local_done", data);
        },
        "sign": function (data) {
            data["action"] = "initial_signature";
            data["socket_id"] = this.socket_id;
            if (data.card !== undefined) {
                this.websocket.send(JSON.stringify(data));
                signatureManager.showLoading();
            } else {
                alertSimple(errorInterpreter(2), gettext("Error"), "error");
                signatureManager.addError(2);
            }
        },
        "complete_sign": function (data) {
            data["action"] = "complete_signature";
            data["socket_id"] = this.socket_id;
            try {
                this.websocket.send(JSON.stringify(data));
            } catch (e) {
                // console.error("Error de comunicación WS");
                signatureManager.hideLoading();
                alertFunction(errorInterpreter(3), gettext("Error"), "error", false, closeModalSignature);
            }
        },

        "validate_document": function (data) {
            data["action"] = "validate_document";
            data["socket_id"] = this.socket_id;
            signatureManager.showLoading();
            try {
                this.websocket.send(JSON.stringify(data));
            } catch (e) {
                signatureManager.hideLoading();
                alertFunction(errorInterpreter(3), gettext("Error"), "error", false, closeModalSignature);
            }
        }
    };
    firmador.inicialize();
    return firmador;
}

function DocumentClient(container, widgetId, signatureManager, url_ws, custom_event) {
    const docmanager = {
        "widgetId": widgetId,
        "container": container,
        "signatureManager": signatureManager,
        "remotesigner": null,
        "localsigner": null,
        "certificates": null,
        "doc_instance": null,
        "logo_url": null,
        "custom_event": custom_event,

        "start_sign": function (doc_instance, logo_url = null) {
            this.doc_instance = doc_instance;
            this.logo_url = logo_url;
            this.localsigner.get_certificates();
            this.signatureManager.clearErrors();
        },
        "success_certificates": function (data) {

            if (data.length > 0) {
                container.querySelector("#container_select_card").classList.remove("d-none");
                container.querySelector("#container_select_card_tem").classList.add("d-none");

                let select_card = container.querySelector(".select_card");

                if (!select_card) {
                    console.error(`Select not found for widget ${widgetId}`);
                    return;
                }
                select_card.innerHTML = "";
                this.certificates = {};

                data.forEach((element) => {
                    this.certificates[element.tokenSerialNumber] = element;
                    let start_token = element.tokenSerialNumber.substring(0, 4);
                    let newOption = new Option(
                        `${start_token} ${element.commonName}`,
                        element.tokenSerialNumber,
                        false, false
                    );
                    select_card.appendChild(newOption);
                });
            } else {
                container.querySelector("#container_select_card").classList.add("d-none");
                container.querySelector("#container_select_card_tem").classList.remove("d-none");
                this.signatureManager.addError(2);
            }
        },

        "do_sign_remote": function () {
            let select = container.querySelector(".select_card");
            let selected_card = select ? select.value : null;

            if (selected_card && this.certificates) {
                let data = {
                    'logo_url': this.logo_url,
                    'instance': this.doc_instance,
                    'card': this.certificates[selected_card],
                    "docsettings": window.pdfSignatureComponents[widgetId].getDocumentSettings()
                };
                this.remotesigner.sign(data);
            } else if (!selected_card && !this.certificates) {
                signatureManager.hideLoading();
                alertSimple(errorInterpreter(1), gettext("Error"), "error");
                this.signatureManager.addError(1);
            } else if (!selected_card && this.certificates) {
                signatureManager.hideLoading();
                alertSimple(errorInterpreter(2), gettext("Error"), "error");
                this.signatureManager.addError(2);
            }

        },

        "do_sign_local": function (data) {
            this.localsigner.sign(data);
        },
        "local_done": function (data) {
            data['instance'] = this.doc_instance;
            data['logo_url'] = this.logo_url;
            this.remotesigner.complete_sign(data);
        },
        "remote_done": function (data) {
            if (data.result !== null) {
                const l = btoa(JSON.stringify({'token': data.result}));
                this.signatureManager.doc_instance['value'] = l;
                this.signatureManager.pdfvisor.urls['renderattr'] = "value=" + l;
                document.getElementById(this.signatureManager.input_id).value = l;
                this.signatureManager.pdfvisor.initPDFViewer();
                signatureManager.hideLoading();
                document.dispatchEvent(this.custom_event);
                alertFunction(
                    gettext("The signing was successfully completed."),
                    gettext("Success"),
                    "success", false, function () {
                    }
                );
            }
        },

        "validate_document_remote": function () {
            data = {
                "instance": this.doc_instance,
            }
            document.dispatchEvent(this.custom_event);
            //this.remotesigner.validate_document(data);
        },

        "validate_document_remote_done": function (reportData) {
            signatureManager.hideLoading();
            if (!reportData || typeof reportData !== 'string') {
                alertFunction(
                    gettext("Please, sign the document before saving"),
                    gettext("Warning"),
                    "warning", false, function () {
                    }
                );
                return;
            }

            if (reportData.includes("no est&aacute; firmado digitalmente")) {
                alertFunction(
                    gettext("The document is not digitally signed. Please sign the document before saving."),
                    gettext("Warning"),
                    "warning", false,
                    function () {
                    }
                );
                return;
            }

            const firmasMatch = reportData.match(/Contiene\s*([\d]+)\s*firma/);
            let numFirmas = 0;
            if (firmasMatch && firmasMatch[1]) {
                numFirmas = parseInt(firmasMatch[1], 10);
            }

            if (numFirmas > 0) {
                if (typeof update_signed_document === "function") {
                    update_signed_document(this.doc_instance);
                } else {
                    console.log("warning: update_signed_document function not defined, using default action");
                    alertFunction(
                        gettext(`The document was saved`),
                        gettext("Success"),
                        "success", false,
                        function () {
                            const container = this.signatureManager.container;
                            const form = container.closest('form');
                            if (form) {
                                form.submit();
                            }
                        }.bind(this)
                    );
                }

            } else {
                alertFunction(
                    gettext("The document is not digitally signed. Please sign the document before saving."),
                    gettext("Warning"),
                    "warning", false,
                    function () {
                    }
                );
            }
        }


    };

    docmanager["remotesigner"] = new FirmadorLibreWS(docmanager, url_ws, signatureManager);
    docmanager["localsigner"] = new FirmadorLibreLocal(docmanager, signatureManager);

    return docmanager;
}

///////////////////////////////////////////////
//  Manage Errors Digital Signature
///////////////////////////////////////////////
function errorInterpreter(error) {

    let textError = "";

    switch (error) {
        case 0:
            // when an uncontrolled error occurs in the signing server
            textError = gettext("An error has occurred in the internal server of the uncontrolled 'Firmador Libre'.");
            break;
        case 1:
            // when the 'Firmador Libre' application fails to open
            textError = gettext("Make sure to start the 'Firmador Libre' application. If it is already running, please press the reload button.");
            break;
        case 2:
            // when there is no card connected
            textError = gettext("There is no card connected to the device. Please press the reload button and connect your card.");
            break;
        case 3:
            // when the signing service is not functioning
            textError = gettext("The internal signature service does not work. Please contact the support.");
            break;
        case 4:
            // when the modal is closed but the PIN entry window remains open
            textError = gettext("Authentication failed because the PIN entry window was detected closed, please try again.");
            break;
        case 5:
            // when the card is disconnected
            //! This error should be resolved within Firmador Libre
            textError = gettext("The device was disconnected, possibly the window was closed for signature. Please close the window for the authentication PIN.");
            break;
        case 6:
            // when the new signature field position overlaps with an existing signature
            textError = gettext("The new signature field position overlaps with an existing signature.");
            break;
        case 7:
            // when the signature is positioned outside the page boundaries
            textError = gettext("The new signature field position is outside the page dimensions.");
            break;
        case 8:
            // when an error occurs due to an incompatible library
            textError = gettext("The version of one or more libraries is incompatible.");
            break;
        case 9:
            // when an error occurs due to an unavailable cryptographic provider
            textError = gettext("The cryptographic provider is not available.");
            break;
        case 10:
            // when an error occurs due to the signing algorithm
            textError = gettext("The signing algorithm is not available.");
            break;
        case 11:
            // when errors occur while serializing data
            textError = gettext("Errors have been encountered in the data to be sent to the 'Free Signer'. Please press the reload button and try again.");
            break;
        case 12:
            // when an error occurs due to a signing service timeout
            textError = gettext("The request to the signing service timed out. Please, press the reload button and try again.");
            break;
        default:
            // when an unknown error occurs
            textError = gettext("We're sorry, an unexpected error occurred. Please, press the reload button and try again.");
    }

    return textError;
}


///////////////////////////////////////////////
//  Alerts Digital Signature
///////////////////////////////////////////////
function alertSimple(text, title = "Error", icon = "error") {
    Swal.fire({
        icon: icon,
        title: title,
        text: text,
        confirmButtonText: gettext("Accept")
    });
}

function alertFunction(text, title = "Error", icon = "error", cancelButton = false,
                       callback = () => {
                       }) {
    Swal.fire({
        icon: icon,
        title: title,
        text: text,
        confirmButtonText: gettext("Accept"),
        showCancelButton: cancelButton,
        cancelButtonText: gettext("Cancel"),
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
    }).then((result) => {
        if (result.isConfirmed) {
            callback();
        }
    });
}

///////////////////////////////////////////////
//  End widgets digital signature
///////////////////////////////////////////////


////////////////////////////////////////////////////////////////
// copy action
////////////////////////////////////////////////////////////////
document.addEventListener("DOMContentLoaded", function () {

    if (document.getElementById("copy-command-line")) {
        document.getElementById("copy-command-line").addEventListener("click", function () {
            let commandText = document.getElementById("command-line").innerText.trim();

            navigator.clipboard.writeText(commandText)
                .then(() => {
                    let text = document.getElementById("text-copy")
                    text.classList.remove("d-none")
                    setTimeout(() => {
                        text.classList.add("d-none")
                    }, 1500)
                })
                .catch(err => {
                    console.error("Error al copiar el texto: ", err);
                });
        });

        document.getElementById("show-command-line").addEventListener("click", () => {
            let container = document.getElementById("container-command-line")

            if (container.classList.contains("d-none")) {
                container.classList.remove("d-none");
            } else {
                container.classList.add("d-none");
            }
        })
    }
});

////////////////////////////////////////////////////////////////
// End copy action
////////////////////////////////////////////////////////////////


class CardList {
  constructor(containerId, apiUrl, actions={}) {
    this.container = document.getElementById(containerId);
    this.apiUrl = apiUrl;
    this.page = 1;
    this.data=null;
    this.page_size = 10;
    this.totalPages = 1;
    this.recordsTotal = 0;
    this.template = '';
    this.filters = {};
    this.actions=actions;
    this.fetchData();

  }

  async fetchData() {
    try {
        const queryParams = new URLSearchParams({
            page: this.page,
            page_size: this.page_size,
            ...(this.filters || {}),
        }).toString();

        const url = `${this.apiUrl}?${queryParams}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);

        const data = await response.json();
        this.template =  data.template || this.template;
        this.totalPages = data.totalPages || 1;
        this.recordsTotal = data.recordsTotal || 0;
        this.process_data(data);
        this.render(data);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
  }

  process_data(data){
    this.data={};
    data.data.forEach(item => {
            this.data[item.id]=item;
    })
  }

  render(data) {
    if (!this.template) {
      console.error("No template found!");
      return;
    }
    this.container.innerHTML = Sqrl.render(this.template, data,  Sqrl.getConfig({ tags: ["<%", "%>"] }));
    gt_find_initialize_from_dom(this.container);
    this.doPagination();
    this.dofiltering();
    this.doPageSizeOptions();
    this.doObjActions()
  }

  async getFilters(){
    const form = this.container.querySelectorAll('.filter_form');

    const result = await convertToStringJson(form);
    this.filters = JSON.parse(result);
    this.fetchData();
  }
  dofiltering(){
  /**
    const forminput = this.container.querySelectorAll('.filter_form input, .filter_form select');
    const parent=this;
    forminput.forEach(input => {
            input.onchange=function(event){
                parent.getFilters();
            }
       });
   **/
  }
  doPageSizeOptions(){
    const formselect = this.container.querySelectorAll('.page_size_select');
    const parent=this;
    parent.page_size=parseInt(formselect[0].value);
    formselect.forEach(input => {
            input.onchange=function(event){
                parent.page_size=event.target.value
                parent.getFilters();
            }
       });

  }
  doPagination(){
    const alink = this.container.querySelectorAll('.pagination a');
    const parent=this;
    alink.forEach(link => {
         link.onclick = function(event) {
         parent.page=event.target.dataset.page;
         parent.fetchData();
         }
    });
  }
  doObjActions(){
    const actions = this.container.querySelectorAll('.obj_action');
    const parent=this;
    actions.forEach(action => {
         action.onclick = function(event) {
            event.preventDefault();
            var pk = action.dataset.instance;
            var name = action.dataset.action;
            if (typeof parent.actions[name] === 'function') {
                parent.actions[name](pk, parent.data[pk]);
            }
         }
    })
    const generalactions = this.container.querySelectorAll('.general_action');
    generalactions.forEach(action => {
         action.onclick = function(event) {
            event.preventDefault();
            var name = action.dataset.action;
            if (typeof parent.actions[name] === 'function') {
                parent.actions[name]();
            }else{
                 if (typeof parent[name] === 'function') parent[name]();
            }
         }
    })
  }
  search(){
     this.getFilters();
  }
  clean(){
    const form = this.container.querySelectorAll('.filter_form');
    clear_action_form(form);
    this.container.querySelectorAll('.filter_form input').forEach(i=>{i.value="";});
    this.getFilters();
  }
}


function build_tagginginput(instances){
    instances.each(function(index, element){
         let tagify = new Tagify(element, {});
         //element.dataset.tagify = JSON.stringify(tagify);
    });
}
function build_tagging_email(instances){
    instances.each(function(index, element){
        let p = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        let tagify = new Tagify(element, {
            pattern: p
        });
    });
}

function build_remote_tagify_email(inputs){
    inputs.each(function(index, element){
       let url = element.dataset['url'];

       let tagify = new Tagify(element, {whitelist:[],
        pattern: /^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})*$/,
         dropdown: {
            searchKeys: ["value", "name"] //  fuzzy-search matching for those whitelist items' properties
         }
       }),
        controller;

        function onInput( e ){
            var value = e.detail.value
              tagify.whitelist = null // reset the whitelist
              // https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort
              controller && controller.abort()
              controller = new AbortController()
              // show loading animation and hide the suggestions dropdown
              tagify.loading(true);
            fetch(url+'?value=' + value, {signal:controller.signal})
                .then(RES => RES.json())
                .then(function(newWhitelist){
                  tagify.whitelist = newWhitelist // update whitelist Array in-place
                  tagify.loading(false); // render the suggestions dropdown
            })
        }
        tagify.on('input', onInput)
    })
}

