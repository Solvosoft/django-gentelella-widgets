//var diction = {}
function get_select2box(instance){
    var select2box = {
    //Template for the options created
    'opt_template': '<option value="new_value">new_display</option>',
    //Instance of the parent container
    'container': null,
    'init': function(){
                let current_instance = this.container
                let parent = current_instance[0] //DOM Container
                let url = current_instance.find('.select2box_available').data('url') //undefined or data
                //Container for the select in options
                let options = parent.getElementsByClassName('select2box_options')[0]
                //Container for the select in available
                let selected_temp = parent.getElementsByClassName('select2box_available form-control')[0]
                //Previously selected values for each element
                let selected_values = current_instance.find('.selected_values_container')[0].innerHTML

                if(url !== undefined){
                    this.remove_all_data(current_instance, options, selected_temp);
                    this.manage_data_api(url, 1, {'selected':[], 'not_selected':[], 'values_selected':selected_values.slice(0, -1)}, current_instance)
                }
                else{
                    this.add_selected(selected_values, current_instance, options);
                }
                this.initialize_elem_func(current_instance, options, selected_temp);
                this.disable_property(current_instance); //Checks if data exists in each select HTML element
            },
    //Fetch the data from an API and inserts it into the options
    'manage_data_api': function(url, page, vals, current_instance){
                        let temp_url = `${url}?page=${page}&selected=${vals['values_selected']}`
                        fetch(temp_url).then(response => response.json()).then(data => {
                            let all_results = data.results
                            for(let e in all_results ) {
                                if (all_results[e]['selected'] && !all_results[e]['disabled']){
                                    vals['selected'].push([all_results[e]['id'], all_results[e]['text']])
                                }
                                else if (!all_results[e]['disabled']){
                                    vals['not_selected'].push([all_results[e]['id'], all_results[e]['text']])
                                }
                            }
                            if(data.pagination.more){
                                let new_page = page+1
                                this.manage_data_api(url, new_page, vals, current_instance)
                            }
                            else{
                                this.insert_api_data(current_instance, vals)
                            }
                          })
                          .catch(error => {
                            console.log("Can't get the API Data, verify the url")
                          });

    },
    //Insert API data in the select elements
    'insert_api_data': function(current_instance, value_dictionary){
                        let temp_opt_format = this.opt_template;
                        let temp_ref = current_instance.find('.select2box_options');
                        let temp_ref_selected = current_instance.find('.select2box_available');
                        let not_selected = value_dictionary['not_selected']
                        let selected = value_dictionary['selected']
                        for(let e in not_selected ) {
                            let temp_format = temp_opt_format.replace('new_value', not_selected[e][0]).replace('new_display', not_selected[e][1])
                            temp_ref.append(temp_format)
                        }
                        for(let e in selected) {
                            let temp_format = temp_opt_format.replace('new_value', selected[e][0]).replace('new_display', selected[e][1])
                            temp_ref_selected.append(temp_format)
                        }
                        this.disable_property(current_instance);
    },
    //Initialize buttons and elements actions
    'initialize_elem_func':function(current_instance, options, selected_temp){
                        current_instance.find('.add_selection')
                            .on("click", () => this.selected_add(current_instance, options));
                        current_instance.find('.select2box_options')
                            .on("dblclick", () => this.selected_add(current_instance, options));
                        current_instance.find('.return_selected')
                            .on("click", () => this.remove_selected(current_instance, selected_temp));
                        current_instance.find('.select2box_available')
                            .on("dblclick", () => this.remove_selected(current_instance, selected_temp));
                        current_instance.find('.all_to_selected')
                            .on('click', () => this.select_all(current_instance, options, '.select2box_available'));
                        current_instance.find('.all_to_available')
                            .on('click', () => this.select_all(current_instance, selected_temp, '.select2box_options'));
                        current_instance.find('.search_select2box')
                            .on('input', () => this.search_data(current_instance, options));
                        current_instance.find('.delete_btn')
                            .on('click', () => this.remove_all_data(current_instance, options, selected_temp));
                        current_instance.find('.save_data_btn')
                            .on('click', () => this.insert_new_data(current_instance));
                        $('#select2box_modal').on('hide.bs.modal', () => {
                                                    //Resets the value of the 2 modal inputs
                                                    current_instance.find('#value_select2box')[0].value = "";
                                                    current_instance.find('#display_select2box')[0].value = "";
                        });
    },
    //Add selected options to the selected container
    'selected_add': function(current_instance, options){
                        let temp_ref = current_instance.find('.select2box_available');
                        let temp_opt_format = this.opt_template;
                        let opt = options.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
                        this.disable_property(current_instance);
    },
    //Add selected options to the available container
    'remove_selected': function(current_instance, selected_temp){
                        let temp_ref = current_instance.find('.select2box_options');
                        let temp_opt_format = this.opt_template;
                        let opt = selected_temp.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
                        this.disable_property(current_instance);
    },
    //Adds all options inside source container to the destination_container (class)
    'select_all': function(current_instance, source, destination_container){
                        let temp_ref = current_instance.find(destination_container)
                        let node_list = source.querySelectorAll('option')
                        let temp_opt_format = this.opt_template;
                        node_list.forEach((e) => {
                          if (!e.hidden){
                            let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                            temp_ref.append(temp_format)
                            e.remove()
                          }
                        })
                        this.disable_property(current_instance);
    },
    //Removes all data from the select HTML elements
    'remove_all_data': function (current_instance, options, selected_temp) {
                        let nodes_available = options.querySelectorAll('option');
                        let nodes_selected = selected_temp.querySelectorAll('option');
                        nodes_available.forEach((e) => {e.remove()});
                        nodes_selected.forEach((e) => {e.remove()});
    },
    //Disables buttons depending on the data in them
    'disable_property': function(current_instance) {
                        let parent = current_instance[0]
                        let options = parent.getElementsByClassName("select2box_options")[0]
                        let selected_temp = parent.getElementsByClassName("select2box_available form-control")[0]
                        let nodes_available = options.querySelectorAll('option').length === 0;
                        let nodes_selected = selected_temp.querySelectorAll('option').length === 0;
                        current_instance.find('.all_to_selected')[0].disabled = (nodes_available);
                        current_instance.find('.add_selection')[0].disabled = (nodes_available);
                        current_instance.find('.all_to_available')[0].disabled = (nodes_selected);
                        current_instance.find('.return_selected')[0].disabled = (nodes_selected);

    },
    //Filters data inside the select_options HTML element
    'search_data': function(current_instance, options) {
                    let search_value = current_instance.find('.search_select2box')[0].value.toLowerCase();
                    let nodes_available = options.querySelectorAll('option')
                    nodes_available.forEach((e) => {
                                        let comp_text = e.innerHTML.toLowerCase()
                                        if (!comp_text.includes(search_value)){
                                            e.hidden = "hidden"
                                        }
                                        else{
                                            e.hidden = ""
                                        }
                                        });
    },
    //Insert new data using the modal inputs
    'insert_new_data': function (current_instance) {
                        let value = current_instance.find('#value_select2box')[0].value;
                        let display = current_instance.find('#display_select2box')[0].value;
                        let temp_opt_format = this.opt_template;
                        let temp_ref = current_instance.find('.select2box_options')
                        if (value !== "" && display !== ""){
                            let temp_format = temp_opt_format.replace('new_value', value).replace('new_display', display);
                            temp_ref.append(temp_format);
                            $('#select2box_modal').modal('hide');
                        }
                        else{
                            alert("Invalid data provided")
                        }
                        this.disable_property(current_instance);
    },
    'selected_all_instances': function() {
                                let all_instances = $(instance).closest('.select2box_container');
                                delete all_instances.prevObject;
                                delete all_instances.length;
                                container_values = Object.keys(all_instances)
                                container_values.forEach((e) => {
                                    temp_container = $(all_instances[e])
                                    let temp_ref = temp_container.find('.select2box_available');
                                    this.form_selected_options(temp_ref[0])

                                })
    },
    'form_selected_options': async function(selected_temp) {
                                let temp_opt_format = this.opt_template;
                                let opt = selected_temp.querySelectorAll('option')
                                opt.forEach((e) => {
                                  e.selected = true
                                });
    },
    'add_selected': function(selected_values, current_instance, options){
                        let temp_ref = current_instance.find('.select2box_available')
                        let nodes_available = options.querySelectorAll('option');
                        let temp_opt_format = this.opt_template;
                        nodes_available.forEach((e) => {
                            let temp_val = e.value
                            let _ = temp_val.toString()
                            if(selected_values.includes(_)){
                                let temp_format = temp_opt_format.replace('new_value', _).replace('new_display', e.innerHTML);
                                temp_ref.append(temp_format);
                                e.remove()
                            }
                        })
    }
    }
    let all_instances = $(instance).closest('.select2box_container')
    delete all_instances.prevObject
    delete all_instances.length
    container_values = Object.keys(all_instances)
    container_values.forEach((e) => {
        let _ = select2box
        _.container = $(all_instances[e])
        _.init()
    })
    select2box.container.closest('form').find('.btn-success').on('click', () => select2box.selected_all_instances())
    return select2box

}
