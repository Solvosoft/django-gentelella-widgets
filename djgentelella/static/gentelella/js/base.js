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
        var datedata =  moment(elem.creation_date).fromNow()
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
        list.html(html);
        list.find('input').iCheck({
            checkboxClass: 'icheckbox_flat-green',
            radioClass: 'iradio_flat-green'
        });
    }
    $(btn).on('click', function(){
        $(form).closest('.x_content').find('.alert').remove();
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

$.fn.select2related = function(action, relatedobjs=[]) {
    /**
        [{ 'id': '#myfield',
          'url': '/myendpoint', * ignored on simple
          'start_empty': true   * only on related action
        }]
    **/
        this.relatedobjs = relatedobjs;
        let parent = this;
        function get_selected_values(obj){
            var data = [];
            $.each(obj, function(i, e){
                if(e.value != "") data.push(e.value);
            });
            return data.join(',');
        }

        if(action === "simple"){
            for(let x=0; x<this.relatedobjs.length; x++){
                $(this.relatedobjs[x]['id']).select2();
            }
        }

        if(action === 'remote'){
            for(let x=0; x<this.relatedobjs.length; x++){
                $(this.relatedobjs[x]['id']).select2({
                      placeholder: 'Select an element',
                      ajax: {
                        url: this.relatedobjs[x]['url'],
                        type: 'GET',
                        dataType: 'json',
                        data: function (params) {
                              var dev= {
                                selected: get_selected_values($(parent.relatedobjs[x]['id']).find(':selected')),
                                term: params.term,
                                page: params.page || 1
                              };
                              $(parent.relatedobjs[x]['id']).trigger('relautocompletedata', dev);
                              return dev;
                        },
                      }
                });
            }
        }
        if(action === "related"){
            for(let x=1; x<this.relatedobjs.length; x++){
                let newselect = $(this.relatedobjs[x]['id']).select2({
                  placeholder: 'Select an element',
                  ajax: {
                    url: this.relatedobjs[x]['url'],
                    type: 'GET',
                    dataType: 'json',
                    data: function (params) {
                      var dev = {
                        relfield: get_selected_values($(parent.relatedobjs[x-1]['id']).find(':selected')),
                        selected: get_selected_values($(parent.relatedobjs[x]['id']).find(':selected')),
                        term: params.term,
                        page: params.page || 1
                      }
                      $(parent.relatedobjs[x]['id']).trigger('relautocompletedata', dev);
                      return dev;
                    },
                  }
                });
                if(parent.relatedobjs[x]['start_empty']){
                    newselect.val(null).trigger('change');
                }
            }

            let newselect = $(this.relatedobjs[0]['id']).select2({
              placeholder: 'Select an element',
              ajax: {
                url: parent.relatedobjs[0]['url'],
                type: 'GET',
                dataType: 'json',
                data: function (params) {
                      return {
                        selected: get_selected_values($(parent.relatedobjs[0]['id']).find(':selected')),
                        term: params.term,
                        page: params.page || 1
                      }
                    },
              }
            });
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

function load_date_range(instance) {
    var options = {
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: 'DD/MM/YYYY',
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'locale': {
                format: 'DD/MM/YYYY',
            }
        }
    }
    return options;
}
function load_datetime_range(instance) {
    var options = {
        'timePicker': true,
        'timePicker24Hour': true,
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: 'DD/MM/YYYY HH:mm A'
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
                format: 'DD/MM/YYYY HH:mm A'
            }
        }
    }
    return options;
}
function load_date_range_custom(instance) {
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
            format: 'DD/MM/YYYY',
        }
    }
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'ranges': {
                'Last 7 Days': [moment(days[0], "DD/MM/YYYY").subtract(6, 'days'), moment(days[0], "DD/MM/YYYY")],
                'Next Week': [moment(days[0], "DD/MM/YYYY"), moment(days[0], "DD/MM/YYYY").add(7, 'days')],
                'Last 30 Days': [moment(days[0], "DD/MM/YYYY").subtract(29, 'days'), moment(days[0], "DD/MM/YYYY")],
                'This Month': [moment(days[0], "DD/MM/YYYY").startOf('month'), moment(days[0], "DD/MM/YYYY").endOf('month')],
                'Last Month': [moment(days[0], "DD/MM/YYYY").subtract(1, 'month').startOf('month'), moment(days[0], "DD/MM/YYYY").subtract(1, 'month').endOf('month')]
            },
            'locale': {
                format: 'DD/MM/YYYY',
            }
        }
    }
    return options;
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
}
