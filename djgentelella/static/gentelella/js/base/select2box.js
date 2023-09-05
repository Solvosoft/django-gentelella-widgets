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
                let form_url = current_instance.find('.select2box_available').data('addurl') //undefined or data
                console.log(url+" --funcion init-- "+form_url)
                //Container for the select in options
                let options = parent.getElementsByClassName('select2box_options')[0]
                //Container for the select in available
                let selected_temp = parent.getElementsByClassName('select2box_available form-control')[0]
                this.url_management(url, current_instance, options, selected_temp)
                this.form_url_management(form_url, current_instance)
                this.initialize_elem_func(current_instance, options, selected_temp); //Initialize all elements in DOM
                this.disable_property(current_instance); //Checks if data exists in each select HTML element
            },
    'url_management': function(url, current_instance, options, selected_temp) {
                        //Previously selected values for each element
                        let selected_values = current_instance.find('.selected_values_container')[0].innerHTML
                        console.log(selected_values+" --funcion url_management-- ")
                        if(url){
                            this.remove_all_data(current_instance, options, selected_temp);
                            this.manage_data_api(url, 1, {'selected':[], 'not_selected':[], 'values_selected':selected_values.slice(0, -1)}, current_instance)
                        }
                        else{
                            this.add_selected(selected_values, current_instance, options);
                        }
    },
    'form_url_management': function(form_url, current_instance){
                        if(form_url){
                            this.create_custom_form(form_url, current_instance)
                            current_instance.find('.save_data_btn').on('click', () => this.send_form_data(form_url, current_instance))
                            console.log(current_instance+" --funcion form_url_management-- ")
                        }
                        else{

                        //Here it is hiding the button that shows the modal with the widget.
                        //I will enable it to be able to see the button.
                            current_instance.find('.create_btn')[0].hidden = 'hidden'
                            //proof
                            //current_instance.find('.create_btn')[0].show = 'show'
                        }
    },
    //Fetch the data from an API and inserts it into the options
    'manage_data_api': function(url, page, vals, current_instance){
                        let temp_url = `${url}?page=${page}&selected=${vals['values_selected']}`
                        console.log(temp_url+" --funcion manage_data_api-- ")
                        fetch(temp_url).then(response => response.json()).then(data => {
                            let all_results = data.results
                            console.log(all_results+" --funcion manage_data_api peticion fetch-- ")
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
                                console.log(new_page+" --funcion manage_data_api nueva pagina-- ")
                                this.manage_data_api(url, new_page, vals, current_instance)
                            }
                            else{
                                this.insert_api_data(current_instance, vals)
                            }
                          })
                          .catch(error => {
                            alert(gettext("Can't get the API Data, verify the url attr"))
                          });
    },
    //Insert API data in the select elements
    'insert_api_data': function(current_instance, value_dictionary){
                        let temp_opt_format = this.opt_template;
                        let temp_ref = current_instance.find('.select2box_options');
                        let temp_ref_selected = current_instance.find('.select2box_available');
                        let not_selected = value_dictionary['not_selected']
                        let selected = value_dictionary['selected']
                        console.log(temp_opt_format+" --funcion insert_api_data-- temp_ref "+temp_ref+" - temp_ref_selected "+temp_ref_selected+" - not_selected "+not_selected+" - selected "+selected)
                        for(let e in not_selected ) {
                            let temp_format = temp_opt_format.replace('new_value', not_selected[e][0]).replace('new_display', not_selected[e][1])
                            temp_ref.append(temp_format)
                            console.log("insert_api_data - temp_format "+temp_format+" - temp_ref "+temp_ref)
                        }
                        for(let e in selected) {
                            let temp_format = temp_opt_format.replace('new_value', selected[e][0]).replace('new_display', selected[e][1])
                            temp_ref_selected.append(temp_format)
                            console.log("insert_api_data - temp_format "+temp_format+" - temp_ref_selected "+temp_ref_selected)
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
                        current_instance.find('.create_btn')
                            .on('click', () => current_instance.find('#select2box_modal').modal('show'));

    },
    //Add selected options to the selected container
    'selected_add': function(current_instance, options){
                        let temp_ref = current_instance.find('.select2box_available');
                        let temp_opt_format = this.opt_template;
                        let opt = options.querySelectorAll(':checked')
                        console.log("selected_add - temp_ref "+temp_ref+" - temp_opt_format"+temp_opt_format+" - opt "+opt)
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
                        console.log("remove_selected - temp_ref "+temp_ref+" - temp_opt_format"+temp_opt_format+" - opt "+opt)
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
                        console.log("select_all - temp_ref "+temp_ref+" - node_list "+node_list+" - temp_opt_format"+temp_opt_format)
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
                        console.log("remove_all_data - nodes_available"+nodes_available+" - nodes_selected"+nodes_selected)
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
                        console.log("disable_property - parent "+parent+" - options "+options+" - selected_temp "+selected_temp+" - nodes_available "+nodes_available+" - nodes_selected "+nodes_selected)
                        current_instance.find('.all_to_selected')[0].disabled = (nodes_available);
                        current_instance.find('.add_selection')[0].disabled = (nodes_available);
                        current_instance.find('.all_to_available')[0].disabled = (nodes_selected);
                        current_instance.find('.return_selected')[0].disabled = (nodes_selected);
    },
    //Filters data inside the select_options HTML element
    'search_data': function(current_instance, options) {
                    let search_value = current_instance.find('.search_select2box')[0].value.toLowerCase();
                    let nodes_available = options.querySelectorAll('option')
                    console.log("search_data - search_value "+search_value+" - nodes_available "+nodes_available)
                    nodes_available.forEach((e) => {
                                        let comp_text = e.innerHTML.toLowerCase()
                                        console.log("nodes_available "+comp_text)
                                        if (!comp_text.includes(search_value)){
                                            e.hidden = "hidden"
                                        }
                                        else{
                                            e.hidden = ""
                                        }
                                        });
    },
    'selected_all_instances': function() {
                                let all_instances = $(instance).closest('.select2box_container');
                                console.log("selected_all_instances - all_instances "+all_instances)
                                //Cleans instance object for selection
                                delete all_instances.prevObject;
                                delete all_instances.length;
                                container_values = Object.keys(all_instances)
                                console.log("container_values "+container_values)
                                container_values.forEach((e) => {
                                    temp_container = $(all_instances[e])
                                    temp_container.find('.select2box_available option').attr('selected', 'selected')
                                })
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
    },
    'create_custom_form': function(url, current_instance) {
                            let modal = current_instance.find('#select2box_modal')
                            console.log("Hola")
                            fetch(url,
                                {credentials: 'include',
                                    headers:{
                                        'X-CSRFToken': this.get_cookie('csrftoken'),
                                    }
                                }).then(response => response.json()).then(data => {
                                modal.append(data.result)
                                gt_find_initialize($(modal))

                                current_instance.find('.save_data_btn').on('click', () => this.send_form_data(url, current_instance))

                            }).catch(error => {
                                current_instance.find('.create_btn')[0].hidden = 'hidden'
                                alert(gettext("Can't get the API Data, verify the addurl attr"))
                            })
    },
    'send_form_data': function(url, current_instance){
                        let form = current_instance.find('.insert_model_data_form')[0]
                        let formData = new FormData(form)
                        const plainFormData = Object.fromEntries(formData.entries());
	                    const formDataJsonString = JSON.stringify(plainFormData);
                        fetch(url, { method: "POST", credentials: 'include',
                          headers: {
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            'X-CSRFToken': this.get_cookie('csrftoken'),
                          },
                          body: formDataJsonString
                        }).then(response => response.json()).then(data => {
                            try{
                                this.insert_new_data(current_instance, data['result'])
                            }catch(error){
                                alert(data['error'])
                            }
                          }).catch(error => {
                                alert(gettext("Can't POST the Data"))
                        });
    },
    //Insert new data using the modal inputs
    'insert_new_data': function (current_instance, new_data) {
                        let temp_opt_format = this.opt_template;
                        let temp_ref = current_instance.find('.select2box_options')
                        let temp_format = temp_opt_format.replace('new_value', new_data.id).replace('new_display', new_data.text);
                        temp_ref.append(temp_format);
                        current_instance.find('#select2box_modal').modal('hide');
                        this.disable_property(current_instance);
    },
    //Get the CSRF Token
    'get_cookie': function(name){
                        return getCookie(name);
    },
    }
    let all_instances = $(instance).closest('.select2box_container')
    delete all_instances.prevObject
    delete all_instances.length
    container_values = Object.keys(all_instances)
    //Iterates through every instance and configure its elements
    container_values.forEach((e) => {
        let _ = select2box
        _.container = $(all_instances[e])
        _.init()
    })
    //Auto selects all data inside selected boxes
    select2box.container.closest('form').find('.btn-success').on('click', () => select2box.selected_all_instances())
    return select2box
}
