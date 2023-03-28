//var diction = {}
function get_select2box(instance){
    var select2box = {
    //Template for the options created
    'opt_template': '<option value="new_value"> new_display </option>',
    //Instance of the parent container
    'container': $(instance).closest('.select2box_container'),
    'options':null,
    'selected_temp': null,
    'init': function(){
                let parent = this.container[0] //DOM Container
                this.options = parent.getElementsByClassName("select2box_options")[0]
                this.selected_temp = parent.getElementsByClassName("select2box_available form-control")[0]
                this.initialize_elem_func();
                this.disable_property(); //Checks if data exists in each select HTML element
                /*
                  this.container.find('.select2box_options').data('url') === undefined or data
                */
            },
    'initialize_elem_func':function(){
                        this.container.find('.add_selection').on("click", () => this.selected_add());
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
    'selected_add': function(){
                        let temp_ref = this.container.find('.select2box_available');
                        let temp_opt_format = this.opt_template;
                        let opt = this.options.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
                        this.disable_property();
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
                        let nodes_available = this.options.querySelectorAll('option').length;
                        let nodes_selected = this.selected_temp.querySelectorAll('option').length;
                        this.container.find('.all_to_available')[0].disabled = (nodes_selected === 0);
                        this.container.find('.all_to_selected')[0].disabled = (nodes_available === 0);

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
                            console.log(temp_format)
                            temp_ref.append(temp_format);
                            $('#select2box_modal').modal('hide');
                        }
                        else{
                            this.container.find('#display_select2box')[0]
                        }
    },
    }
    select2box.init()
    return select2box

}
