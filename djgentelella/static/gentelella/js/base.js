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
            var $this=$(e),
                $parentdiv=$this.closest('.input-group'),
                upload_url = $this.data('href'),
                field_name = $this.attr('name'),
                div_message = $parentdiv.find($this.data('message')),
                div_process = $parentdiv.find($this.data('process')),
                url_done = $this.data('done'),
                input_token = $this.data('inputtoken'),
                fileshow = $parentdiv.find('.fileshow'),
                uploadfilecontent = $parentdiv.find('.uploadfilecontent'),
                removecheck = $this.closest('.fileupload').find('input[data-widget="CheckboxInput"]');

           $this.attr("required", false);
           div_message.hide();
           fileshow.on('click', function(){
                uploadfilecontent.toggle();
                div_message.toggle();
           });
           removecheck.on('ifToggled', function(event){
               if(this.checked){
                    $parentdiv.find('input[name="'+input_token+'"]').val("0");
               }else{
                 if( $parentdiv.find('input[name="'+input_token+'"]').val() == "0"){
                    $parentdiv.find('input[name="'+input_token+'"]').val("");
                 }
               }
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

function gtforms(index,manager, formList, extra=true)  {
    return {
        index: index,
        order: index,
        manager: manager,
        formList: formList,
        extra: extra,
        instance: null,
        deleteForm: function(){
          if( !this.manager.validateDeleteForm()) {
            this.manager.notify('error', 'You can not delete this form, minimum form validation failed' )
            return;
          }
            this.instance.hide();
            this.instance.find('input[name="'+this.manager.prefix+'-'+this.index+'-DELETE"]').prop( "checked", true );
            this.manager.deleteForm(this.order);
        },
        render: function(){
            var html = this.manager.template.replace(/__prefix__/gi, this.index);
            this.instance = $(html);
            formList.append(this.instance);
            this.initializeWidgets(this.instance);
            this.registerBtns();

        },
        reorder: function(oper){
            var brother = this.manager.getForm(this.order+oper);
            this.manager.switchFrom(this.order, this.order+oper);
            if(brother != null){
                if(oper == 1 ){
                    this.instance.before(brother.instance);
                }else{
                    brother.instance.before(this.instance);
                }
            }
        },
        registerBtns: function(){
            this.instance.find('.deletebtn').on('click', this.callDelete(this));
            // down increment order and up decrement order when forms are inserted in bottom
            this.instance.find('.btndown').on('click', this.callReorder(this, 1));
            this.instance.find('.btnup').on('click', this.callReorder(this, -1));
        },
        callDelete: function(instance){
            return () => { instance.deleteForm() };
        },
        initializeWidgets: function(instance){
            gt_find_initialize(instance);
        },
        callReorder: function(instance, oper){
            return () => { instance.reorder(oper) }
        },
        updateOrder: function(){
            this.instance.find('input[name="'+this.manager.prefix+'-'+this.index+'-ORDER"]').val(this.order);
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
        initialize: function(){
         this.template = this.formsetControl.find(".formsettemplate").contents()[0].data;
         this.prefix = this.formsetControl.data('prefix');
         this.validateMax = this.formsetControl.data('validate-max') == '1';
         this.validateMin = this.formsetControl.data('validate-min') == '1';
         this.loadManagementForm();
         this.instance.find('.formsetadd').on('click', this.addBtnForm(this));
         this.addFormDom();
        },
        addBtnForm: function(instance){
            return () => { instance.addEmtpyForm()  };
        },
        addEmtpyForm: function(){
            if(this.validateAddForm()){
                var form = gtforms(this.index, this, this.formList);
                form.render();
                this.forms.push(form);
                this.index += 1;
                this.updateTotalForms(+1);
            }else{
                this.notify('error', 'You cannot add new form, limit is exceded')
            }
        },
        addForm: function(object){},
        addFormDom: function(){
            this.formList.children().each((i, element) =>{
                 var form = gtforms(this.index, this, this.formList, extra=false);
                 form.instance = $(element);
                 form.registerBtns();
                 this.forms.push(form);
                 this.index += 1;
            });
        },
        deleteForm: function(index){
            if( !this.validateDeleteForm()) return;
            if(index>=0 && index < this.forms.length){
                if(this.forms[index].extra){
                    this.forms.splice(index, 1);
                    this.updateTotalForms(-1);
                    if(index == this.forms.length){
                        this.index -= 1;
                    }else{
                        for(var x=0; x<this.forms.length; x++){
                            this.forms[x].order = x;
                            this.forms[x].updateOrder();
                        }
                    }
                }

            }
        },
        validateAddForm: function(){
            if(!this.validateMax) return true;
            return this.MAX_NUM_FORMS == -1 || this.TOTAL_FORMS < this.MAX_NUM_FORMS;
        },
        validateDeleteForm: function(){
            if(!this.validateMin) return true;
            return this.MIN_NUM_FORMS == -1 || this.TOTAL_FORMS > this.MIN_NUM_FORMS;
        },
        loadManagementForm: function(){
            this.TOTAL_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val());
            this.INITIAL_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val());
            this.MIN_NUM_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val());
            this.MAX_NUM_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val());
        },
        updateManagementForm: function(){
            this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val(this.INITIAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val(this.MIN_NUM_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val(this.MAX_NUM_FORMS);
        },
        updateTotalForms: function(oper){
            this.TOTAL_FORMS = this.TOTAL_FORMS+oper;
            this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
        },
        getForm: function(index){
            if(index>=0 && index < this.forms.length){
                return this.forms[index];
            }
            return null;
        },
        switchFrom: function(fref, fswap){
            var freform = this.getForm(fref);
            var fswapform = this.getForm(fswap);
            if(freform != null && fswapform != null){
                var tmporder = freform.order;
                freform.order = fswapform.order;
                fswapform.order = tmporder;
                freform.updateOrder();
                fswapform.updateOrder();

                this.forms.sort((a, b) => a.order - b.order);
                this.redrawOrdering();
            }

        },
        redrawOrdering: function(){
            for(var x=0; x<this.forms.length; x++){
                 this.formList.append(this.forms[x].instance);
            }
        },
        notify: function(type, text){
            console.log(text);
        },
        clean: function(){
            while(this.forms.length>0){
                var f = this.forms.pop();
                f.instance.remove();
            }
            this.TOTAL_FORMS=0;
            this.INITIAL_FORMS=0;
            this.TOTAL_FORMS=0;
            this.index=0;
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
            console.log(obj.attr('data-target-to'));
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

    instance.ionRangeSlider({
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

