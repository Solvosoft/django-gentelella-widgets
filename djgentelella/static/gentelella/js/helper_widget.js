class HelperBox {
    constructor(instance,box, configs){
        this.instance = instance
        this.box = box;
        this.configs = configs;

    }
    /**
    this.configs ={
    help_url: "/api/ayuda/"
    id_view: "agresion-p1"
    permissions: Object { "djgentelella.add_help": true, "djgentelella.change_help": true, "djgentelella.view_help": true }
    }
    */
    hide_elements(){
        $("#helper-body").find(".helperitem").hide();
    }

    get_help_list(hide=false){
        let parent = this;
        $.getJSON(this.configs.help_url+"?id_view="+this.configs.id_view,
            function(data){
                for(var i=0; i < data.length; i++){
                    parent.add_element(data[i]);
                }
                if(hide){
                    parent.hide_elements()
                }
            } );
    }

    add_element(data){
        let parent = this;
        var protohtml = $('#helper-prototype').html();
        let repl_list = [["$title", 'help_title'],
                        ["$text", 'help_text'],
                        ["$id_view", 'id_view'],
                        ["$id_question", 'question_name'],
                        ["$id_pk", 'id']
                        ];
        for( let key of repl_list){
            protohtml = protohtml.replace(key[0], data[key[1]] )
        }
        var byline = '';
        if (this.has_perm('djgentelella.change_help')){
            byline = '<button class="btn btn-xs btn-edit" ><i class="fa fa-edit blue"></i></button>';
        }
        if (this.has_perm('djgentelella.delete_help')){
            byline += '<button class="btn btn-xs btn-del" ><i class="fa fa-minus-circle red"></i></button>';
        }
        protohtml = protohtml.replace('<div class="byline">$byline </div>', byline)
        var instance = $(protohtml);
        instance.find('.btn-edit').on('click', this.show_edit_modal(this));
        $('#helper-body').append(instance);

        //console.log(protohtml);

    }
    has_perm(perm){
        let dev = true;
        if(this.configs.permissions.hasOwnProperty(perm)){
            dev = this.configs.permissions[perm];
        }

       return dev;
    }
    show_edit_modal(parent){

      return  function(){
        var item = $(this).closest('.helperitem');
        let modal =$("#modal_"+parent.instance);
        modal.find('input[name="help_title"]').val(item.find(".title").html());
        modal.find('textarea[name="help_text"]').val(item.find(".excerpt").html());
        modal.find('input[name="pk"]').val(item.data('id-item'));
        modal.find('input[name="id_view"]').val(item.data('id_view'));
        modal.find('input[name="question_name"]').val(item.data('id_question'));
        modal.find('input[name="ftype"]').val("edit");
        $("#modal_"+parent.instance).modal('show');
      }
    }
}

$.fn.helper_box = function($elemid){
     var helperbox = new HelperBox($elemid, this, document.help_widget);
     helperbox.get_help_list();
}
