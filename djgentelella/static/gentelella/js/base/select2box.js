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
                        this.container.find('.all_to_available').on('click', () => this.select_all(this.selected_temp, '.select2box_options'))
                     },
    //Add selected options to the selected container
    'selected_add': function(){
                        let temp_ref = this.container.find('.select2box_available');
                        let temp_opt_format = this.opt_template;
                        let opt = this.options.querySelectorAll(':checked')
                        opt.forEach((e) => {
                          //console.log("Index:", e.value, "Disp:", e.innerHTML, e)
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        });
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
                    },
    //Adds all options inside source container to the destination_container (class)
    'select_all': function(source, destination_container){
                        let temp_ref = this.container.find(destination_container)
                        let node_list = source.querySelectorAll('option')
                        let temp_opt_format = this.opt_template;
                        node_list.forEach((e) => {
                          let temp_format = temp_opt_format.replace('new_value', e.value).replace('new_display', e.innerHTML)
                          temp_ref.append(temp_format)
                          e.remove()
                        })
    },
    }
    select2box.init()
    return select2box

}
