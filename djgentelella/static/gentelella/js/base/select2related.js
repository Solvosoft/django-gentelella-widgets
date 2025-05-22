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
