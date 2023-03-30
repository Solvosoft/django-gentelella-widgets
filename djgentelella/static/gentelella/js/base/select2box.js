//var diction = {}
function get_select2box(instance){
    var select2box = {
    //Template for the options created
    'opt_template': '<option value="new_value"> new_display </option>',
    //Instance of the parent container
    'container': null,
    'options':null,
    'selected_temp': null,
    'init': function(){
                let current_instance = this.container
                let parent = current_instance[0] //DOM Container
                let url = current_instance.find('.select2box_available').data('url') //undefined or data
                let options = parent.getElementsByClassName("select2box_options")[0]
                let selected_temp = parent.getElementsByClassName("select2box_available form-control")[0]
                if(url !== undefined){
                    this.get_api_data(url, current_instance, options, selected_temp)
                }
                this.initialize_elem_func(current_instance, options, selected_temp);
                this.disable_property(current_instance, options, selected_temp); //Checks if data exists in each select HTML element
            },
    //Fetch the data from an API and inserts it into the options
    'get_api_data': function(url, current_instance, options, selected_temp){
                        let value_dictionary = {};
                        fetch(url).then(response => response.json()).then(data => {
                            let key_to_use = Object.keys(data.results[0])[0];
                            for(let e in data.results ) {
                                //console.log(e, Object.keys(data.results[e])[0]);
                                value_dictionary[e] = data.results[e][key_to_use]
                            }
                            this.remove_all_data(current_instance, options, selected_temp);
                            this.insert_api_data(current_instance, value_dictionary);
                          })
                          .catch(error => {
                            //console.error('Error:', error);
                            console.log("Can't get the API Data, verify the url")
                          });
                        console.log(current_instance)
                        console.log(value_dictionary)
    },
    'insert_api_data': function(current_instance, value_dictionary){
                        let temp_opt_format = this.opt_template;
                        let temp_ref = current_instance.find('.select2box_options');
                        for(let e in value_dictionary ) {
                            let temp_format = temp_opt_format.replace('new_value', e).replace('new_display', value_dictionary[e])
                            temp_ref.append(temp_format)
                        }
    },
    'initialize_elem_func':function(current_instance, options, selected_temp){
                        current_instance.find('.add_selection')
                            .on("click", () => {this.selected_add(current_instance, options), this.disable_property(current_instance, options, selected_temp);});
                        current_instance.find('.select2box_options').on("dblclick", () => this.selected_add(current_instance, options));
                        current_instance.find('.return_selected').on("click", () => this.remove_selected(current_instance, selected_temp));
                        current_instance.find('.select2box_available').on("dblclick", () => this.remove_selected(current_instance, selected_temp));
                        current_instance.find('.all_to_selected').on('click', () => this.select_all(current_instance, options, '.select2box_available'));
                        current_instance.find('.all_to_available').on('click', () => this.select_all(current_instance, selected_temp, '.select2box_options'));
                        current_instance.find('.search_select2box').on('input', () => this.search_data(current_instance, options));
                        current_instance.find('.delete_btn').on('click', () => this.remove_all_data(current_instance, options, selected_temp));
                        current_instance.find('.save_data_btn').on('click', () => this.insert_new_data(current_instance));
                        $('#select2box_modal').on('hide.bs.modal', () => {
                                                    //Resets the value of the 2 modal inputs
                                                    current_instance.find('#value_select2box')[0].value = "";
                                                    current_instance.find('#display_select2box')[0].value = "";
                        })
                     },

    //Add selected options to the selected container
    'selected_add': function(current_instance, options){
                        console.log(options)
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
                        this.disable_property(current_instance);
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
    }
    let all_instances = $(instance).closest('.select2box_container')
    delete all_instances.prevObject
    delete all_instances.length
    //console.log(all_instances)
    container_values = Object.keys(all_instances)
    container_values.forEach((e) => {
        let _ = select2box
        _.container = $(all_instances[e])
        _.init()
    })
    return select2box

}
