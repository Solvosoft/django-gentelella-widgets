function convertFormToJSON(form, prefix="") {
  const re = new RegExp("^"+prefix);
  return form
    .serializeArray()
    .reduce(function (json, { name, value }) {
      json[name.replace(re, "")] = value;
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
function BaseFormModal(modalid, datatableelement,  data_extras={}, relinstance_display={})  {
    var modal = $(modalid);
    var form = modal.find('form');
    var prefix = form.find(".form_prefix").val();
    if(prefix.length != 0){
        prefix = prefix+"-"
    }
    return {
        "instance": modal,
        "relinstance_display": relinstance_display,
        "reloadtable": true,
        "form": form,
        "url": form[0].action,
        "prefix": prefix,
        "type": "POST",
        "btn_class": ".formadd",
        "data_extras": data_extras,
        "init": function(){
            var myModalEl = this.instance[0];
            myModalEl.addEventListener('hidden.bs.modal', this.hidemodalevent(this))
            this.instance.find(this.btn_class).on('click', this.add_btn_form(this));

        },
        "add_btn_form": function(instance){
            return function(event){
                fetch(instance.url, {
                    method: instance.type,
                    body: convertToStringJson(instance.form, prefix=instance.prefix, extras=instance.data_extras),
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
                    if (instance.reloadtable){
                        datatableelement.ajax.reload();
                    }
                    instance.hidemodal();
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
            if(errors.hasOwnProperty('detail') && Object.keys(errors).length == 1){
                Swal.fire({ icon: 'error', title: gettext('Error'), text: errors.detail });
            }
            instance.form.find('ul.form_errors').remove();
            form_field_errors(instance.form, errors, instance.prefix);
        },
        "handle_error": function(instance, error){
            Swal.fire({ icon: 'error', title: gettext('Error'), text: error.message });
        },
        "hidemodal": function(){
            this.instance.modal('hide');
        },
        "hidemodalevent": function(instance){
            return function(event){
                clear_action_form(instance.form);
                instance.hidemodal();
            }
        },
        "showmodal": function(btninstance){
            this.instance.modal('show');
        },
        "fillForm": function(datainstance){
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
                     if(instance.relinstance_display.hasOwnProperty(e)){
                        display_name_key=instance.relinstance_display[e];
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
            if (item.length>0){
                if(item.attr('type') === "checkbox" ){
                    item.prop( "checked", value);
                }else if(item.attr('type') === "radio"){
                    var sel = item.filter(function() { return this.value == value });
                    sel.prop( "checked", true);
             } else {  item.val(value); }
            }
       }
    }
}
/**


**/

function BaseDetailModal(modalid, base_detail_url, template_url){
    return {
        "modal": $(modalid),
        "modalid": modalid,
        "instanceid": null,
        "template_url": template_url,
        "base_detail_url": base_detail_url,
        "template": "{{it.display_text}}",
        "template_max_tries": 1,
        "detail_max_tries": 1,
        "template_tries": 0,
        "detail_tries": 0,
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
                instance.template=data['template'];
            }
        },
        "update_detail": function(instance){
            return function(data){
                 instance.detail_tries=0;
                 var result = Sqrl.render(instance.template,  data);
                 instance.modal.find(".modal-body").html(result);
                 instance.show();
            }
        },
        "recall_get_template": function(instance){
            return function(response) {
                if(instance.template_tries<instance.template_max_tries){
                    instance.template_tries = instance.template_tries+ 1;
                    instance.get_template();
                }
            }
        },
        "recall_get_detail": function(instance){
            return function(response) {
                if(instance.detail_tries<instance.detail_max_tries){
                    instance.detail_tries = instance.detail_tries+1;
                    instance.show_instance(instance.instanceid);
                }
            }

        },
        "get_template": function(){
            var instance = this;
            fetch(instance.template_url, {
                  method: "get",
                  headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'}
                }
                ).then(response_manage_type_data(instance, instance.error, instance.handle_error))
                .then(instance.update_template(instance))
                .catch(instance.recall_get_template(instance));
        },
        "show_instance": function(instanceid){
            var instance = this;
            if(this.instanceid != instanceid){ instance.detail_tries = 0; }
            this.instanceid = instanceid
            var url = this.base_detail_url.replace('/0/', '/'+instanceid+'/');

            fetch(url, {
                method: "get",
                headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'}
                }
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

function ObjectCRUD(uniqueid, urls, datatableelement, modalids, actions, datatableinits,
    replace_as_detail={create: false,  update: true, destroy: true, list: false },
    addfilter=false, relinstance_display={}, data_extras={}
){
/**
actions:   {
    instance_action: [],
    obj_action: [
        {
                action: function ( e, dt, node, config ) {},
                text: '<i class="fa fa-eraser" aria-hidden="true"></i>',
                titleAttr: gettext('Clear Filters'),
                className: this.header_btn_class
        }
    ]

}

*/

    per_instance_actions = []
    per_obj_action = []
    if( "instance_action" in actions){
        per_instance_actions=actions.instance_action;
    }
    if( "obj_action" in actions){
        per_obj_action = actions.obj_action;
    }
    obj={
        "uniqueid": uniqueid,
        "display_text": relinstance_display,
        "can_create": modalids.hasOwnProperty("create"),
        "can_destroy": urls.hasOwnProperty("destroy_url") && modalids.hasOwnProperty("destroy") ,
        "can_list": urls.hasOwnProperty("list_url"),
        "can_detail": urls.hasOwnProperty("detail_url") && modalids.hasOwnProperty("detail") && urls.hasOwnProperty("detail_template_url"),
        "can_update": modalids.hasOwnProperty("update"),
        "use_update_values": urls.hasOwnProperty("update_values_url"),
        "header_btn_class": 'btn-sm mr-4',
        "datatable": null,
        "create_form": null,
        "update_form": null,
        "delete_form": null,
        "data_extras": data_extras,
        "detail_modal": null,
        "base_update_url":null,
        "instance_actions": per_instance_actions,
        "obj_action": per_obj_action,
        "init": function(){
            if(this.can_list) this.list();
            if(this.can_create){
                this.obj_action.push({
                    action: this.create(this),
                    text: '<i class="fa fa-plus" aria-hidden="true"></i>',
                    titleAttr: gettext('Create'),
                    className: this.header_btn_class
                })
                this.create_form = BaseFormModal(modalids.create, this.datatable, data_extras=this.data_extras);
                this.create_form.init();
            }
            if(this.can_update){
                this.update_form = BaseFormModal(modalids.update, this.datatable,
                 data_extras=this.data_extras, relinstance_display=this.display_text);
                this.update_form.type = "PUT";
                this.base_update_url = this.update_form.url;
                this.update_form.init();
            }
            if(this.can_detail){
                this.detail_modal = BaseDetailModal(modalids.detail, urls.detail_url, urls.detail_template_url)
                this.detail_modal.init()
            }
            if(this.can_destroy){
                this.destroy_form = BaseFormModal(modalids.destroy, this.datatable,
                 data_extras=this.data_extras, relinstance_display=this.display_text);
                this.destroy_form.type = "DELETE";
                this.destroy_form.btn_class = ".delbtn";
                this.destroy_form.init();
            }
        },
        "create":  function(instance){
            return function(e, dt, node, config){
                instance.create_form.showmodal();
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
        "error": function(instance){
            return function(response) {
                let error_msg = gettext('There was a problem performing your request. Please try again later or contact the administrator.');  // any other error
                  if(response.type === "basic" ){
                      Swal.fire({
                            title: gettext('Error'),
                            text: error_msg + gettext(" status ") +response.statusText,
                            icon: 'error'
                        });
                        return response;
                  } else {
                   response.json().then(data => {  // there was something in the response from the API regarding validation
                        if(data['detail']){
                            error_msg = data['detail'];  // specific api validation errors
                        }
                    })
                    .finally(() => {
                        Swal.fire({
                            title: gettext('Error'),
                            text: error_msg,
                            icon: 'error'
                        });
                    });
                }
            }
        },
        "destroy": function(data, action) {
            let url =  urls.destroy_url.replace('/0/', '/'+data.id+'/');
            let text = gettext("This Object")
            this.destroy_form.url = url;
            this.destroy_form.instance.find(".objtext").html(text)
            this.destroy_form.showmodal();
        },
        "list": function(){
            /**
                This function initialize datatable
            */
            var instance = this;
            if(this.can_list){
              this.obj_action.unshift({
                action: function ( e, dt, node, config ) {clearDataTableFilters(dt, id)},
                text: '<i class="fa fa-eraser" aria-hidden="true"></i>',
                titleAttr: gettext('Clear Filters'),
                className: this.header_btn_class
             })
            }
            if(!datatableinits.hasOwnProperty("buttons")){
                datatableinits['buttons'] = this.obj_action;
            }
            if(this.can_detail){
                instance.instance_actions.push(
                    {
                     'name': "detail",
                     'action': 'detail',
                     'url': null,
                     'i_class': 'fa fa-eye',
                    }
                )
            }
            if(this.can_update){
                instance.instance_actions.push(
                    {
                     'name': "update",
                     'action': 'update',
                     'url': null,
                     'i_class': 'fa fa-edit',
                    }
                )
            }
            if(this.can_destroy){
                instance.instance_actions.push(
                    {
                     'name': 'destroy',
                     'action': 'destroy',
                     'url': null,
                     'i_class': 'fa fa-trash',
                    }
                )
            }
            if(!datatableinits.hasOwnProperty("columns")){
                datatableinits.columns=[];
            }
            if(!datatableinits.hasOwnProperty("columnDefs")){
                datatableinits['columnDefs'] = [
                    {
                    targets: -1,
                    title: gettext('Actions'),
                    type: 'actions',
                    className: "no-export-col",
                    orderable: false,
                    render: function(data, type, full, meta){
                        var edittext = '<div class="d-flex mt-1">';
                            for(var x=0; x<instance.instance_actions.length; x++){
                              let params = "'"+instance.uniqueid+"', "+x+", "+meta.row
                              edittext += '<i onclick="javascript:call_obj_crud_event('+params+');"';
                              edittext += ' class="'+instance.instance_actions[x].i_class+'" ></i>';
                            }

                        edittext += '</div>';
                        return edittext;
                     }
                }
                ]
            }
         this.datatable = createDataTable(datatableelement, urls.list_url, datatableinits, addfilter=addfilter);

        },
        "detail":  function(instance, action){
                this.detail_modal.show_instance(instance.id);
        },
        "update": function(instance, action){
            if(this.use_update_values){
                let url =  urls.update_values_url.replace('/0/', '/'+instance.id+'/');
                this.retrieve_data(url, 'GET', this.update_value_success(this, instance),
                this.error(this));
            }else{
                this.update_value_success(this, instance)(instance);
            }
        },
        "update_value_success": function(instance, element){
            return function(data){
                instance.update_form.fillForm(data);
                instance.update_form.url = instance.base_update_url.replace('/0/', '/'+data.id+'/');
                instance.update_form.showmodal();
            }
        },
        "action_update": function(action, data){},
        "action_destroy": function(action, data){},
        'do_instance_action': function(action_position, instance_id){
           var instance = this;
           var data = this.datatable.row(instance_id).data(); ;
           if(action_position>=0 && action_position<instance.instance_actions.length){
                let action=instance.instance_actions[action_position];
                if(action.name in this){
                    this[action.name](data, action);
                }else{
                    this.do_action(data, action);
                }
           }
        },
        'do_action': function(data, action){
            let method = 'method' in action ? action.method : 'POST';
            let body = 'data_fn' in action ? JSON.stringify(action.data_fn(data)) : '';
            if( 'url' in action  &&  action.url !== null){
                fetch(action.url, {
                    method: method,
                    body: body,
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'}
                    }
                ).then(response => {
                    if(response.ok){ return response.json(); }
                    return Promise.reject(response);  // then it will go to the catch if it is an error code
                })
                .then(instance.success(instance))
                .catch(instance.error(instance));
            }
        },
        'retrieve_data': function(url, method, success, error){
                fetch(url, {
                    method: method,
                   // body: body,
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json'}
                }).then(response => {
                    if(response.ok){ return response.json(); }
                    return Promise.reject(response);  // then it will go to the catch if it is an error code
                })
                .then(success)
                .catch(error);
        }
    };
    gt_crud_objs[uniqueid] = obj;
    return obj;
}

function call_obj_crud_event(uniqueid, action_position, row_id){
    if(uniqueid in gt_crud_objs){
        gt_crud_objs[uniqueid].do_instance_action(action_position, row_id)
    }
}
