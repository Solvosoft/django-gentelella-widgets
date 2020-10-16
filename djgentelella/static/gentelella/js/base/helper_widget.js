
class HelperBox {
    constructor(instance,box, configs){
        this.instance = instance
        this.box = box;
        this.configs = configs;
        $("#modal_"+instance+"_btn").on('click', this.send_edit_data(this));
        this.add_tool_active = false;
        this.add_commands_toolbar();
        this.hide_edit_button();
        let widthx='50%';
        if($(window).width() < 502){
            widthx='90%';
        }

        $("#content_"+this.instance).css(
        {'position': 'fixed',
        'bottom':  '35px', 'left': '50px', 'width': widthx, 'z-index': 10000});
        $(".btnsavedel").on('click', this.delete_element_save(this));
    }
    /**
    this.configs ={
    help_url: "/api/ayuda/"
    id_view: "agresion-p1"
    permissions: Object { "djgentelella.add_help": true, "djgentelella.change_help": true, "djgentelella.view_help": true }
    }
    */
    hide_palette(){
        $("#content_"+this.instance).collapse('hide');
    }
    hide_elements(){
        $("#helper-body").find(".helperitem").hide();
    }
    show_elements(){
        $("#helper-body").find(".helperitem").show();
    }
    hide_edit_button(){
       if(!(this.has_perm('djgentelella.change_help')|| this.has_perm('djgentelella.delete_help'))){
            $("#expand_"+this.instance).hide();
       }
       if(!this.has_perm('djgentelella.add_help')){
           $("#show_help_"+this.instance).hide();
       }


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
    delete_element_save(parent){
        return function(){
            var pk = $('.formdelitem input[name="pk"]').val();
            let question_name = $('.formdelitem input[name="question_name"]').val();
            let url = parent.configs.help_url;
            $.ajax({
                url: url+pk,
                //data: form.serialize(),
                type: "DELETE",
                headers: {'X-CSRFToken': getCookie('csrftoken') },
                success: function(){
                    $('#helper-body').find('[data-id_question="'+question_name+'"]').remove();
                    var label = $('label[for="'+question_name+'"]');
                    var icon = label.closest(".helpbtn").find('i');
                    icon.remove();
                    label.unwrap();
                    $("#del_modal_"+parent.instance).modal('hide');
                    parent.hide_palette();
                    parent.show_elements();
                },
                error: function(error){
                    console.log(error);
                }
            });
        }
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
        protohtml = protohtml.replace('$byline', byline)
        var instance = $(protohtml);
        instance.find('.btn-edit').on('click', this.show_edit_modal(this));
        instance.find('.btn-del').on('click', this.show_delete_modal(this));
        $('#helper-body').append(instance);
        this.add_label_icon(data);
        //console.log(protohtml);

    }
    has_perm(perm){
        let dev = false;
        if(this.configs.permissions.hasOwnProperty(perm)){
            dev = this.configs.permissions[perm];
        }

       return dev;
    }
    show_palette(){
        $("#content_"+this.instance).collapse('show');
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
    send_edit_data(parent){
        return function(){
            let modal = $(this).closest('.modal');
            let form = modal.find('form');
            let url = parent.configs.help_url;
            let verb = 'POST';
            let pk = form.find('input[name="pk"]').val();
            if(pk != ''){
                url = url+pk;
                verb = 'PUT';
            }

            $.ajax({
                url: url,
                data: form.serialize(),
                type: verb,
                headers: {'X-CSRFToken': getCookie('csrftoken') },
                success: function(result){
                    $('[data-id-item="'+result['id']+'"]').remove();
                    parent.add_element(result);
                    modal.modal('hide');
                },
                error: function(error){
                    console.log(error);
                }
            })
        }
    }
    add_start_label_icon(){
        let parent = this;
        if(!parent.add_tool_active){
            $(".right_col").find('label').each(function(i, e){
                let item = $(e);
                let forlabel = item.attr('for');
                if(item.parent().attr('class') != "helpbtn" && parent.has_perm('djgentelella.change_help')){
                    item.wrap('<div class="helpbtn" data-question_name="'+forlabel+'"></div>' );
                    let img = $('<i class="fa fa-question-circle help_i"></i>');
                    img.on('click', parent.show_help_in_box(parent, forlabel));
                    item.closest('.helpbtn').prepend(img);
                }
            });
        }else{
            var inotgreen = $(".helpbtn").find("i:not(.green)");
            var label = inotgreen.closest(".helpbtn").find('label');
            inotgreen.remove();
            label.unwrap();

        }
        }
    add_label_icon(data){
        let parent = this;
        let item = $('label[for="'+data.question_name+'"]');
        if(item.parent().attr('class') != "helpbtn"){
            item.wrap('<div class="helpbtn" data-question_name="'+data.question_name+'"></div>' );
            let img = $('<i class="fa fa-question-circle green help_i"></i>&nbsp;');
            img.on('click', this.show_help_in_box(this, data.question_name));
            item.closest('.helpbtn').prepend(img);
        }else{
            item.closest(".helpbtn").find('.help_i').addClass('green');
        }
    }
    show_help_in_box(parent, question_name){
        return function(){
            let qname = $('[data-id_question="'+question_name+'"]');
            if(qname.length>0){
                parent.hide_elements();
                qname.show();
                parent.show_palette();
            }else{
                let label = $('label[for="'+question_name+'"]');
                let modal =$("#modal_"+parent.instance);
                modal.find('input[name="help_title"]').val(label.text());
                modal.find('textarea[name="help_text"]').val("");
                modal.find('input[name="pk"]').val("");
                modal.find('input[name="id_view"]').val(parent.configs.id_view);
                modal.find('input[name="question_name"]').val(question_name);
                modal.find('input[name="ftype"]').val("add");
                $("#modal_"+parent.instance).modal('show');
            }
        }
    }
    add_commands_toolbar(){
        let parent = this;
        $("#show_help_"+this.instance).on('click', function(){
            parent.add_start_label_icon();
            parent.add_tool_active = !parent.add_tool_active;
            return false;
        });

 $("#expand_"+parent.instance).on('click', function(){
     let instance = $("#content_"+parent.instance);
     let iint = $("#expand_"+parent.instance+" i");

     $(".byline").toggle();
 });




    }
    show_delete_modal(parent){
        return function(){
            var item = $(this).closest('.helperitem');
            $('.formdelitem input[name="pk"]').val(item.data('id-item'));
            $('.formdelitem input[name="question_name"]').val(item.data('id_question'));

            $('.delp').html(item.find(".title").html());
            $("#del_modal_"+parent.instance).modal();

        }
    }
}

$.fn.helper_box = function($elemid){
     var helperbox = new HelperBox($elemid, this, document.help_widget);
     helperbox.get_help_list();
}


interact('.resize-drag')
  .resizable({
    // resize from all edges and corners
    edges: { left: true, right: true, bottom: true, top: true },

    listeners: {
      move (event) {
        var target = event.target
        var x = (parseFloat(target.getAttribute('data-x')) || 0)
        var y = (parseFloat(target.getAttribute('data-y')) || 0)

        // update the element's style
        target.style.width = event.rect.width + 'px'
        target.style.height = event.rect.height + 'px'

        $('#helper-body').css('height',(event.rect.height-50) + 'px');

        // translate when resizing from top or left edges
        x += event.deltaRect.left
        y += event.deltaRect.bottom

        target.style.webkitTransform = target.style.transform =
          'translate(' + x + 'px,' + y + 'px)'

        target.setAttribute('data-x', x)
        target.setAttribute('data-y', y)
      }
    },
    modifiers: [
      // keep the edges inside the parent
      interact.modifiers.restrictEdges({
        outer: 'parent'
      }),

      // minimum size
      interact.modifiers.restrictSize({
        min: { width: 150, height: 350 }
      })
    ],

    inertia: true
  })
  .draggable({
    listeners: { move: window.dragMoveListener },
    inertia: true,
    modifiers: [
      interact.modifiers.restrictRect({
        restriction: 'parent',
        endOnly: true
      })
    ]
  })