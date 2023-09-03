function convertFormToJSON(form, prefix="") {
  const re = new RegExp("^"+prefix);
  var selectmultipleitems = [];
  form.find("select").each(function(i,e){
        if($(e).prop('multiple')){
            selectmultipleitems.push(e.name.replace(re, ""));
        }
  });

  return form
    .serializeArray()
    .reduce(function (json, { name, value }) {
      let clean_name = name.replace(re, "");
      if(json.hasOwnProperty(clean_name)){
         if(Array.isArray(json[clean_name])){
            json[clean_name].push(value);
         }else{
            let oldvalue = json[clean_name];
            json[clean_name]=[];
            json[clean_name].push(oldvalue);
         }
      }else{
         if(selectmultipleitems.indexOf(clean_name) !== -1){
            json[clean_name] = [value];
         }else{
            json[clean_name] = value;
         }
      }
      return json;
    }, {});
}

function convertToStringJson(form, prefix="", extras={}){
    var formjson =convertFormToJSON(form, prefix=prefix);
    formjson=Object.assign({}, formjson, extras)
    return JSON.stringify(formjson);
}

function load_errors(error_list, obj){
    ul_obj = "<ul class='errorlist form_errors d-flex justify-content-center'>";
    error_list.forEach((item)=>{
        ul_obj += "<li>"+item+"</li>";
    });
    ul_obj += "</ul>"
    $(obj).parents('.form-group').prepend(ul_obj);
    return ul_obj;
}

function form_field_errors(target_form, form_errors, prefix){
    var item = "";
    for (const [key, value] of Object.entries(form_errors)) {
        item = " #id_" +prefix+key;
        if(target_form.find(item).length > 0){
            load_errors(form_errors[key], item);
        }
    }
}

function response_manage_type_data(instance, err_json_fn, error_text_fn){
    return function(response) {
        const contentType = response.headers.get("content-type");
        if(response.ok){
             if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            }else{
                return response.text();
            }
        }else{
            if (contentType && contentType.indexOf("application/json") !== -1) {
                response.json().then(data => err_json_fn(instance, data));
            }else{
                response.text().then(data => error_text_fn(instance, data));
            }
            return Promise.resolve(false);
        }

        return Promise.reject(response);  // then it will go to the catch if it is an error code
    }
}

function clear_action_form(form){
    // clear switchery before the form reset so the check status doesn't get changed before the validation
    $(form).find("input[data-switchery=true]").each(function() {
        if($(this).prop("checked")){  // only reset it if it is checked
            $(this).trigger("click").prop("checked", false);
        }
    });

    $(form).trigger('reset');
    $(form).find("select option:selected").prop("selected", false);
    $(form).find("select").val(null).trigger('change');
    $(form).find("ul.form_errors").remove();
}

var gt_form_modals = {}
var gt_detail_modals = {}
var gt_crud_objs = {};

function  gt_show_actions(crud_name){
     return function(data, type, row, meta){
        var html="";
        if(data != null ){
            if(data.title != undefined){
                html+= data.title+" ";
            }
            for(var x=0; x<data.actions.length; x++){
                let action = data.actions[x];
                html += '<i onclick="javascript:call_obj_crud_event(\''+crud_name+'\', \''+action.name+'\', '+meta.row+');" class="'+action.i_class+'"></i>';
            }
        }
        return html;
    }
}

function GTBaseFormModal(modal_id, datatable_element,  form_config)  {
    var modal = $(modal_id);
    var form = modal.find('form');
    var prefix = form.find(".form_prefix").val();
    if(prefix.length != 0){
        prefix = prefix+"-"
    }
    const default_config = {
        "btn_class": ".formadd",
        "type": "POST",
        "reload_table": true,
        "events": {'form_submit': function(instance){ return {} },
                   'success_form': function(data){},
                   'error_form': function(errors){}

                  },
        "relation_render": {}
   }


    const config =  Object.assign({}, default_config, form_config);

    return {
        "instance": modal,
        "relation_render": config.relation_render,
        "reload_table": config.reload_table,
        "config": config,
        "form": form,
        "url": form[0].action,
        "prefix": prefix,
        "type": config.type,
        "btn_class": config.btn_class,
        "init": function(){
            var myModalEl = this.instance[0];
            myModalEl.addEventListener('hidden.bs.modal', this.hide_modalevent(this))
            this.instance.find(this.btn_class).on('click', this.add_btn_form(this));

        },
        "add_btn_form": function(instance){
            return function(event){
                fetch(instance.url, {
                    method: instance.type,
                    body: convertToStringJson(instance.form, prefix=instance.prefix,
                            extras=instance.config.events.form_submit(instance)),
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'}
                    }
                    ).then(response_manage_type_data(instance, instance.error, instance.error_text))
                    .then(instance.fn_success(instance))
                    .catch(error => instance.handle_error(instance, error));
            }
        },
        "success": function(instance, data){
        },
        "fn_success": function(instance){
           return function(data){
                if(data !== false){
                    instance.config.events.success_form(data)
                    if (instance.reload_table){
                        datatable_element.ajax.reload();
                    }
                    instance.hide_modal();
                    Swal.fire({
                        icon: 'success',
                        title: gettext('Success'),
                        text: data.detail,
                        timer: 1500
                    });
                    instance.success(instance, data);
                }
           }
        },
        "error_text": function(instance, message){
            Swal.fire({icon: 'error',  title: gettext('Error'),  text: message });
        },
        "error": function(instance, errors){
            instance.config.events.error_form(errors)
            if(errors.hasOwnProperty('detail') && Object.keys(errors).length == 1){
                Swal.fire({ icon: 'error', title: gettext('Error'), text: errors.detail });
            }
            instance.form.find('ul.form_errors').remove();
            form_field_errors(instance.form, errors, instance.prefix);
        },
        "handle_error": function(instance, error){
            Swal.fire({ icon: 'error', title: gettext('Error'), text: error.message });
        },
        "hide_modal": function(){
            this.instance.modal('hide');
        },
        "hide_modalevent": function(instance){
            return function(event){
                clear_action_form(instance.form);
                instance.hide_modal();
            }
        },
        "show_modal": function(btninstance){
            this.instance.modal('show');
        },
        "fill_form": function(datainstance){
            var keys  = Object.keys(datainstance);
            var select2Items = [];
            var instance = this;
            $.each(keys, function(i, e){
                if($("#id_"+instance.prefix+e).data('select2-id') != undefined ){
                  select2Items.push(e);
                }else{
                   instance.updateInstanceForm(instance.prefix+e, datainstance[e]);
                }

             });
             // do select 2 items
             $.each(select2Items, function(i, e){
                     var display_name_key = 'display_name';
                     if(instance.relation_render.hasOwnProperty(e)){
                        display_name_key=instance.relation_render[e];
                     }
                      $('#id_'+instance.prefix+e).val(null).trigger('change');
                      if(datainstance[e]){
                        if(Array.isArray(datainstance[e])){
                            for(var x=0; x<datainstance[e].length; x++){
                                var newOption = new Option(datainstance[e][x][display_name_key], datainstance[e][x]['id'], true, true);
                                $('#id_'+instance.prefix+e).append(newOption);
                            }
                        }else{
                            if($('#id_'+instance.prefix+e+' option[value="'+datainstance[e]['id']+'"]').length>0){
                                $('#id_'+instance.prefix+e).val(datainstance[e]['id']);
                            }else{
                                var newOption = new Option(datainstance[e][display_name_key], datainstance[e]['id'], true, true);
                                $('#id_'+instance.prefix+e).append(newOption);
                            }
                        }
                        $('#id_'+instance.prefix+e).trigger('change')
                      }
            });
        },
        "updateInstanceForm": function (name, value){
            var item = this.form.find('input[name="'+name+'"], textarea[name="'+name+'"]');

            item.each(function(i, inputfield){
                let done=false;
                inputfield=$(inputfield);
                if(inputfield.attr('type') === "checkbox" ){
                    inputfield.prop( "checked", value);
                    done=true;
                } else if(inputfield.attr('type') === "radio"){
                    var sel = inputfield.filter(function() { return this.value == value });
                    sel.prop( "checked", true);
                    done=true;
                }
                if (inputfield.data().widget === "EditorTinymce"){
                     tinymce.get(inputfield.attr('id')).setContent(value);
                     done=true;
                }
                if(!done) { inputfield.val(value); }
            });
       }
    }
}
/**
**/

function BaseDetailModal(modalid, base_detail_url, template_url, form_config={}){
    const default_config = {
        "base_template": "{{it.display_text}}",
        "title": "{{it.title}}",
        "template_max_tries": 1,
        "detail_max_tries": 1,
        "headers": {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'},
        "method": "get",
        "events": {
                   'update_detail_event': function(data){ return data},
                   'form_submit_template': function(data){ return data},
                   'form_submit_instance': function(data){ return data},
                   'form_error_instance': function(errors){},
                   'form_error_template': function(errors){}
        }
   }


    const config =  Object.assign({}, default_config, form_config);
    return {
        "modal": $(modalid),
        "modalid": modalid,
        "config" : config,
        "instanceid": null,
        "template_url": template_url,
        "base_detail_url": base_detail_url,
        "template": config.base_template,
        "title": config.title,
        "template_max_tries": config.template_max_tries,
        "detail_max_tries": config.detail_max_tries,
        "template_tries": 0,
        "detail_tries": 0,
        "title": config.title,
        "init": function(){
            this.get_template();
        },
        "show": function(){
            this.modal.modal('show');
        },
        "hide": function(){
            this.modal.modal('hide');
        },
        "update_template": function(instance){
            return function(data){
                instance.template_tries=0;
                instance.template= 'template' in data ? data['template'] : instance.template;
                instance.title = 'title' in data ? data['title'] : instance.title;
            }
        },
        "update_detail": function(instance){
            return function(data){
                 data = instance.config.events.update_detail_event(data);
                 instance.detail_tries=0;
                 var result = Sqrl.render(instance.template,  data);
                 instance.modal.find(".modal-body").html(result);
                 var result = Sqrl.render(instance.title,  data);
                 instance.modal.find(".modal-title").html(result);
                 instance.show();
            }
        },
        "recall_get_template": function(instance){
            return function(response) {
                if(instance.template_tries<instance.template_max_tries){
                    instance.template_tries = instance.template_tries+ 1;
                    instance.get_template();
                }else{
                    instance.config.events.form_error_template(response);
                }
            }
        },
        "recall_get_detail": function(instance){
            return function(response) {
                if(instance.detail_tries<instance.detail_max_tries){
                    instance.detail_tries = instance.detail_tries+1;
                    instance.show_instance(instance.instanceid);
                }else{
                    instance.config.events.form_error_instance(response);
                }
            }

        },
        "get_template": function(){
            var instance = this;
            let params = {
                  method: instance.config.method,
                  headers: instance.config.headers
                }
            params = instance.config.events.form_submit_template(params);

            fetch(instance.template_url, params
                ).then(response_manage_type_data(instance, instance.error, instance.handle_error))
                .then(instance.update_template(instance))
                .catch(instance.recall_get_template(instance));
        },
        "show_instance": function(instanceid){
            var instance = this;
            if(this.instanceid != instanceid){ instance.detail_tries = 0; }
            this.instanceid = instanceid
            var url = this.base_detail_url.replace('/0/', '/'+instanceid+'/');

            let params = {
                  method: instance.config.method,
                  headers: instance.config.headers
                }
            params = instance.config.events.form_submit_instance(params);
            fetch(url, params
                ).then(response_manage_type_data(instance, instance.error, instance.handle_error))
                .then(instance.update_detail(instance))
                .catch(instance.recall_get_detail(instance));

        },
        "error": function(instance, errors){
            Swal.fire({ icon: 'error', title: gettext('Error'), text: errors.detail });
        },
        "handle_error": function(instance, error){
            Swal.fire({ icon: 'error', title: gettext('Error'), text: error.message });
        },

    }
}

function ObjectCRUD(uniqueid, objconfig={}){

    var default_config = {
        uls: null,
        datatable_element: null,
        modal_ids: null,
        events: {
             'update_data': function(data){ return data; }
        },
        actions: { table_actions: [],  object_actions: [],
                    title: gettext('Actions'),
                    className:  "no-export-col"
                    },
        datatable_inits: {},
        replace_as_detail: {create: false,  update: true, destroy: true, list: false },
        relation_render: {},
        headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'},
        btn_class: {
            create: 'btn-sm mr-4'
        },
        icons: {
            create: '<i class="fa fa-plus" aria-hidden="true"></i>',
            clear: '<i class="fa fa-eraser" aria-hidden="true"></i>',
            detail: 'fa fa-eye',
            update: 'fa fa-edit',
            destroy: 'fa fa-trash'
        },
        delete_display: function(data){ return gettext("This Object"); },
        gt_form_modals: {
            'create': {},
            'detail': {},
            'update': {},
            'destroy': {}
        }

    }

    const config =  Object.assign({}, default_config, objconfig);

    per_table_actions = []
    per_object_actions = []
    if( "table_actions" in objconfig.actions){
        per_table_actions=objconfig.actions.table_actions;
    }
    if( "object_actions" in objconfig.actions){
        per_object_actions = objconfig.actions.object_actions;
    }
    obj={
        "uniqueid": uniqueid,
        "config": config,
        "relation_render": config.relation_render,
        "can_create": config.modal_ids.hasOwnProperty("create"),
        "can_destroy": config.urls.hasOwnProperty("destroy_url") && config.modal_ids.hasOwnProperty("destroy") ,
        "can_list": config.urls.hasOwnProperty("list_url"),
        "can_detail": objconfig.urls.hasOwnProperty("detail_url") && config.modal_ids.hasOwnProperty("detail")
        && config.urls.hasOwnProperty("detail_template_url"),
        "can_update": config.modal_ids.hasOwnProperty("update"),
        "use_get_values_for_update": config.urls.hasOwnProperty("get_values_for_update_url"),
        "create_btn_class": config.btn_class.create,
        "datatable": null,
        "create_form": null,
        "update_form": null,
        "delete_form": null,
        "data_extras": config.data_extras,
        "detail_modal": null,
        "base_update_url":null,
        "table_actions": per_table_actions,
        "object_actions": per_object_actions,
        "init": function(){
            if(this.can_list) this.list();
            if(this.can_create){
                let create_conf = Object.assign({}, {}, this.config.gt_form_modals.create);
                this.create_form = GTBaseFormModal(this.config.modal_ids.create, this.datatable, create_conf);
                this.create_form.init();
            }
            if(this.can_update){
                let update_conf = Object.assign({}, {
                    type: "PUT",  relation_render: this.relation_render
                }, this.config.gt_form_modals.update);
                this.update_form = GTBaseFormModal(this.config.modal_ids.update, this.datatable, update_conf);
                this.base_update_url = this.update_form.url;
                this.update_form.init();
            }
            if(this.can_detail){
                let detail_conf = Object.assign({}, {}, this.config.gt_form_modals.detail);
                this.detail_modal = BaseDetailModal(this.config.modal_ids.detail,
                                                    this.config.urls.detail_url,
                                                    this.config.urls.detail_template_url,
                                                    detail_conf)
                this.detail_modal.init()
            }
            if(this.can_destroy){
                let destroy_conf = Object.assign({}, {
                    type: "DELETE", relation_render: this.relation_render, btn_class: ".delbtn"
                }, this.config.gt_form_modals.destroy);
                this.destroy_form = GTBaseFormModal(this.config.modal_ids.destroy, this.datatable, destroy_conf);
                this.destroy_form.init();
            }
        },
        "create":  function(instance){
            return function(e, dt, node, config){
                instance.create_form.show_modal();
            }
        },
        "success": function(instance){
            return function(data){
                Swal.fire({
                    title: gettext('Success'),
                    text: data['detail'],
                    icon: 'success',
                    timer: 1500
                });
                instance.datatable.ajax.reload();
            }

        },
        "destroy": function(data, action) {
            let url =  this.config.urls.destroy_url.replace('/0/', '/'+data.id+'/');
            let text = this.config.delete_display(data)
            this.destroy_form.url = url;
            this.destroy_form.instance.find(".objtext").html(text)
            this.destroy_form.show_modal();
        },
        "list": function(){
            /**
                This function initialize datatable
            */
            var instance = this;

            if(this.can_create){
                this.table_actions.push({
                    action: this.create(this),
                    text: this.config.icons.create,
                    titleAttr: gettext('Create'),
                    className: this.config.create
                })
            }
            if(this.can_list){
              this.table_actions.unshift({
                action: function ( e, dt, node, config ) {clearDataTableFilters(dt, instance.config.datatable_element)},
                text: this.config.icons.clear,
                titleAttr: gettext('Clear Filters'),
                className: this.header_btn_class
             })
            }
            if(!config.datatable_inits.hasOwnProperty("buttons")){
                config.datatable_inits['buttons'] = this.table_actions;
            }
            if(this.can_detail){
                instance.object_actions.push(
                    {
                     'name': "detail",
                     'action': 'detail',
                     'url': null,
                     'i_class': this.config.icons.detail,
                    }
                )
            }
            if(this.can_update){
                instance.object_actions.push(
                    {
                     'name': "update",
                     'action': 'update',
                     'url': null,
                     'i_class': this.config.icons.update,
                    }
                )
            }
            if(this.can_destroy){
                instance.object_actions.push(
                    {
                     'name': 'destroy',
                     'action': 'destroy',
                     'url': null,
                     'i_class': this.config.icons.destroy,
                    }
                )
            }
            if(!config.datatable_inits.hasOwnProperty("columns")){
                config.datatable_inits.columns=[];
            }
            if(!config.datatable_inits.hasOwnProperty("columnDefs")){
                config.datatable_inits['columnDefs'] = [
                    {
                    targets: -1,
                    title: this.config.actions.title,
                    type: 'actions',
                    className: this.config.actions.className,
                    orderable: false,
                    render: function(data, type, full, meta){
                        var edittext = '<div class="d-flex mt-1">';
                            for(var x=0; x<instance.object_actions.length; x++){
                               let action = instance.object_actions[x];
                               let display_in_column = true;
                              if('in_action_column' in action ){
                                    display_in_column=action.in_action_column;
                              }
                              if(display_in_column){
                                 let params = "'"+instance.uniqueid+"', '"+action.name+"', "+meta.row;
                                 edittext += '<i onclick="javascript:call_obj_crud_event('+params+');"';
                                 edittext += ' class="'+instance.object_actions[x].i_class+'" ></i>';
                              }

                            }
                        edittext += '</div>';
                        return edittext;
                     }
                }
                ]
            }
         this.datatable = gtCreateDataTable(this.config.datatable_element, this.config.urls.list_url,
                                            this.config.datatable_inits);
        },
        "detail":  function(instance, action){
                this.detail_modal.show_instance(instance.id);
        },
        "update": function(instance, action){
            if(this.use_get_values_for_update){
                let url =  this.config.urls.get_values_for_update_url.replace('/0/', '/'+instance.id+'/');
                this.retrieve_data(url, 'GET', this.update_value_success(this, instance));
            }else{
                this.update_value_success(this, instance)(instance);
            }
        },
        "update_value_success": function(instance, element){
            return function(data){
                data = instance.config.events.update_data(data);
                instance.update_form.fill_form(data);
                instance.update_form.url = instance.base_update_url.replace('/0/', '/'+data.id+'/');
                instance.update_form.show_modal();
            }
        },
        "action_update": function(action, data){},
        "action_destroy": function(action, data){},
        'do_table_actions': function(action_position){
           var instance = this;
           if(action_position>=0 && action_position<instance.table_actions.length){
                let action=instance.table_actions[action_position];
                if(action.name in this){
                    this[action.name]({}, action);
                }else{
                    this.do_action({}, action);
                }
           }
        },
        'do_object_actions': function(action_position, instance_id){
           var instance = this;
           var data = this.datatable.row(instance_id).data(); ;
           if(action_position>=0 && action_position<instance.object_actions.length){
                let action=instance.object_actions[action_position];
                if(action.name in this){
                    this[action.name](data, action);
                }else{
                    this.do_action(data, action);
                }
           }
        },
        'do_action': function(data, action){
            var instance = this;
            let method = 'method' in action ? action.method : 'POST';
            let body = 'data_fn' in action ? JSON.stringify(action.data_fn(data)) : '';
            let error_fn = 'error_fn' in action ? action.error_fn : instance.error;
            if( 'url' in action  &&  action.url !== null){
                fetch(action.url, {
                    method: method,
                    body: body,
                    headers: this.config.headers
                    }
                ).then(response_manage_type_data(instance, error_fn, instance.error_text))
                .then(instance.success(instance))
                .catch(instance.error(instance));
            }
        },
        'retrieve_data': function(url, method, success){
            var instance = this;
            fetch(url, {
                    method: method,
                    headers:this.config.headers
                }).then(response_manage_type_data(instance, instance.error, instance.error_text))
                .then(success)
                .catch(error => instance.handle_error(instance, error));
        },
        "error_text": function(instance, message){
            Swal.fire({icon: 'error',  title: gettext('Error'),  text: message });
        },
        "error": function(instance, errors){
            if(errors.hasOwnProperty('detail') && Object.keys(errors).length == 1){
                Swal.fire({ icon: 'error', title: gettext('Error'), text: errors.detail });
            }
            //instance.form.find('ul.form_errors').remove();
            //form_field_errors(instance.form, errors, instance.prefix);
        },
        "handle_error": function(instance, error){
            let error_msg = gettext('There was a problem performing your request. Please try again later or contact the administrator.');
            Swal.fire({ icon: 'error', title: error_msg, text: error.message });
        },
        'find_table_action_by_name': function(name){
            for(var x=0; x<this.table_actions.length; x++){
                if(this.table_actions[x].name === name){
                    return x;
                }
            }
            return undefined;
        },
        'find_object_action_by_name': function(name){
            for(var x=0; x<this.object_actions.length; x++){
                if(this.object_actions[x].name === name){
                    return x;
                }
            }
            return undefined;
        }

    };
    gt_crud_objs[uniqueid] = obj;
    return obj;
}

function call_obj_crud_event(uniqueid, action_name, row_id){
    if(uniqueid in gt_crud_objs){
        let position = gt_crud_objs[uniqueid].find_object_action_by_name(action_name);
        if(position != undefined){
            gt_crud_objs[uniqueid].do_object_actions(position, row_id);
        }
    }
}

function call_table_crud_event(uniqueid, action_name){
    if(uniqueid in gt_crud_objs){
         let position = gt_crud_objs[uniqueid].find_table_action_by_name(action_name);
         if(position != undefined){
            gt_crud_objs[uniqueid].do_table_actions(position, 0);
         }
    }
}

