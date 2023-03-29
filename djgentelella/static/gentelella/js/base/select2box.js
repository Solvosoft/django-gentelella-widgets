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
                let parent = this.container[0] //DOM Container
                console.log(this.container)
                let url = this.container.find('.select2box_available').data('url') //undefined or data
                if(url !== undefined){
                    this.get_api_data(url)
                }
                this.options = parent.getElementsByClassName("select2box_options")[0]
                this.selected_temp = parent.getElementsByClassName("select2box_available form-control")[0]
                this.initialize_elem_func(this);
                this.disable_property(); //Checks if data exists in each select HTML element
            },
    //Fetch the data from an API and inserts it into the options
    'get_api_data': function(url){
                        let value_dictionary = {};
                        fetch(url).then(response => response.json()).then(data => {
                            let key_to_use = Object.keys(data.results[0])[0];
                            for(let e in data.results ) {
                                //console.log(e, Object.keys(data.results[e])[0]);
                                value_dictionary[e] = data.results[e][key_to_use]
                            }
                            this.insert_api_data(value_dictionary);
                          })
                          .catch(error => {
                            //console.error('Error:', error);
                            console.log("Can't get the API Data, verify the url")
                          });
                        console.log(value_dictionary)
    },
    'insert_api_data': function(value_dictionary){
                        let temp_opt_format = this.opt_template;
                        let temp_ref = this.container.find('.select2box_options');
                        this.remove_all_data();
                        for(let e in value_dictionary ) {
                            let temp_format = temp_opt_format.replace('new_value', e).replace('new_display', value_dictionary[e])
                            temp_ref.append(temp_format)
                        }
    },
    'initialize_elem_func':function(obj){
                        this.container.find('.add_selection').on("click", () => obj.selected_add(obj));
                        this.container.find('.select2box_options').on("dblclick", () => this.selected_add());
                        this.container.find('.return_selected').on("click", () => this.remove_selected());
                        this.container.find('.select2box_available').on("dblclick", () => this.remove_selected());
                        this.container.find('.all_to_selected').on('click', () => this.select_all(this.options, '.select2box_available'));
                        this.container.find('.all_to_available').on('click', () => this.select_all(this.selected_temp, '.select2box_options'));
                        this.container.find('.search_select2box').on('input', () => this.search_data());
                        this.container.find('.delete_btn').on('click', () => this.remove_all_data());
                        this.container.find('.save_data_btn').on('click', () => this.insert_new_data());
                        $('#select2box_modal').on('hide.bs.modal', () => {
                                                    //Resets the value of the 2 modal inputs
                                                    this.container.find('#value_select2box')[0].value = "";
                                                    this.container.find('#display_select2box')[0].value = "";
                        })
                     },

    //Add selected options to the selected container
    'selected_add': function(obj){
                        console.log(obj)
                        let temp_ref = obj.container.find('.select2box_available');
                        let temp_opt_format = obj.opt_template;
                        let opt = obj.options.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
                        obj.disable_property();
                    },
    //Add selected options to the available container
    'remove_selected': function(){
                        let temp_ref = this.container.find('.select2box_options');
                        let temp_opt_format = this.opt_template;
                        let opt = this.selected_temp.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
                        this.disable_property();
                    },
    //Adds all options inside source container to the destination_container (class)
    'select_all': function(source, destination_container){
                        let temp_ref = this.container.find(destination_container)
                        let node_list = source.querySelectorAll('option')
                        let temp_opt_format = this.opt_template;
                        node_list.forEach((e) => {
                          if (!e.hidden){
                            let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                            temp_ref.append(temp_format)
                            e.remove()
                          }
                        })
                        this.disable_property();
    },
    //Removes all data from the select HTML elements
    'remove_all_data': function () {
                        let nodes_available = this.options.querySelectorAll('option');
                        let nodes_selected = this.selected_temp.querySelectorAll('option');
                        nodes_available.forEach((e) => {e.remove()});
                        nodes_selected.forEach((e) => {e.remove()});
    },
    //Disables buttons depending on the data in them
    'disable_property': function() {
                        let nodes_available = this.options.querySelectorAll('option').length === 0;
                        let nodes_selected = this.selected_temp.querySelectorAll('option').length === 0;
                        this.container.find('.all_to_available')[0].disabled = (nodes_selected);
                        this.container.find('.all_to_selected')[0].disabled = (nodes_available);
                        this.container.find('.add_selection')[0].disabled = (nodes_available);
                        this.container.find('.return_selected')[0].disabled = (nodes_selected);

    },
    //Filters data inside the select_options HTML element
    'search_data': function() {
                    let search_value = this.container.find('.search_select2box')[0].value.toLowerCase();
                    let nodes_available = this.options.querySelectorAll('option')
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
    'insert_new_data': function () {
                        let value = this.container.find('#value_select2box')[0].value;
                        let display = this.container.find('#display_select2box')[0].value;
                        let temp_opt_format = this.opt_template;
                        let temp_ref = this.container.find('.select2box_options')
                        if (value !== "" && display !== ""){
                            let temp_format = temp_opt_format.replace('new_value', value).replace('new_display', display);
                            temp_ref.append(temp_format);
                            $('#select2box_modal').modal('hide');
                        }
                        else{
                            alert("Invalid data provided")
                        }
    },
    }
    let all_instances = $(instance).closest('.select2box_container')
    delete all_instances.prevObject
    delete all_instances.length
    console.log(all_instances)
    container_values = Object.keys(all_instances)
    container_values.forEach((e) => {
        let _ = select2box
        _.container = $(all_instances[e])
        _.init()
    })
    return select2box

}
