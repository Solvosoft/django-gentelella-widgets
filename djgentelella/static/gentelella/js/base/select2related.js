function is_hide_selected(instance){
    /**
      select2 4.1 dropped the `hideSelected` option that 3.x had, so an already
      chosen entry keeps showing in the dropdown of a multiple select (it only
      gets the `select2-results__option--selected` class). We bring the old
      behaviour back, on by default for multiples, off with
      `data-hide-selected="false"`.
    **/
    if(!instance.prop('multiple')) return false;
    return instance.data('hide-selected') !== false;
}

function filter_selected_results(instance, data){
    /**
      Drops from an ajax payload the entries the backend flagged as already
      selected. Must run *after* add_selected_option(), which needs them to
      rebuild the <option> nodes. `pagination.more` is left untouched so
      select2's infinite scroll keeps asking for the next page.
    **/
    if(!is_hide_selected(instance)) return data;
    if(!data || !Array.isArray(data.results)) return data;
    data.results = data.results.filter(function(item){ return !item.selected; });
    return data;
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
    if(is_hide_selected(instance)){
        // Static (non ajax) selects build their results from the <option>
        // nodes, so there is no payload to filter: the css class hides the
        // ones select2 already marked as selected.
        context.dropdownCssClass = ((context.dropdownCssClass || '') +
                                    ' gt-hide-selected').trim();
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

function bind_auto_reset_children(relatedobjs){
    /**
      `data-autoresetchildren` on a select of a related group: every time the
      user changes it, every select further down the chain is emptied, so a
      stale canton can't survive a change of province.

      It listens to select2's own select/unselect/clear events instead of
      `change`: add_selected_option() triggers `change` while the chain is
      still initializing, and that would wipe the bound values on page load.
    **/
    for(let x=0; x<relatedobjs.length; x++){
        let elem = $(relatedobjs[x]['id']);
        // A re-render (formset clone, reopened modal, api_list.js) runs
        // gt_find_initialize again over the same ids, so drop our previous
        // handler without touching anybody else's.
        elem.off('.gtautoreset');
        if(!relatedobjs[x]['auto_reset_children']) continue;
        elem.on('select2:select.gtautoreset select2:unselect.gtautoreset ' +
                'select2:clear.gtautoreset', function(){
            for(let y=x+1; y<relatedobjs.length; y++){
                let child = $(relatedobjs[y]['id']);
                if(child.val() === null || child.val() === '' ||
                   (Array.isArray(child.val()) && child.val().length === 0)){
                    continue;
                }
                child.val(null).trigger('change');
            }
        });
    }
}

window.extract_select2_context=extract_select2_context;
$.fn.select2related = function(action, relatedobjs=[]) {
    /**
        [{ 'id': '#myfield',
          'url': '/myendpoint', * ignored on simple
          'start_empty': true,  * only on related action
          'auto_reset_children': true  * only on related action
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
                            return filter_selected_results($(parent.relatedobjs[x]['id']), data);
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
                        return filter_selected_results($(parent.relatedobjs[x]['id']), data);
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
                    return filter_selected_results($(parent.relatedobjs[0]['id']), data);
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
            // ['s2'], not ['id']: overwriting the selector string with the
            // jQuery object breaks every later consumer of relatedobjs[0].id
            // (add_selected_option, the relfield lookup, auto reset children).
            this.relatedobjs[0]['s2']=newselect;
            if(this.relatedobjs[0]['start_empty']){
                newselect.val(null).trigger('change');
            }
            bind_auto_reset_children(this.relatedobjs);
        }
        return this;
    };
