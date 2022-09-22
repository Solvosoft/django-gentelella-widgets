$.fn.notificationWidget = function(){

    update_instance = function(url, pk){
        $.ajax({
            url: url+pk,
            data: {'state': 'hide'},
            type: "PUT",
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            success: function(){ },
            error: function(error){
                console.log(error);
            }
        });
    }
    delete_instance = function(url, pk){
        $.ajax({
            url: url+pk,
            //data: form.serialize(),
            type: "DELETE",
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            success: function(){ },
            error: function(error){
                console.log(error);
            }
        });
    }
    on_click_clk =  function(base, elem, parent, instance){

        return function(event){

              instance.do_not_hide = true;
              var action = $(this).data('action');
              if('hide' == action){
                parent.update_instance(instance.data('apiurl'),  elem.id);
              }
              if( 'delete' == action){
                parent.delete_instance(instance.data('apiurl'), elem.id);
              }
              base.remove();
              var count = parseInt(instance.find('.notificacionnumero').text());
              count -= 1;
              instance.find('.notificacionnumero').text(count);

        }
    }
    create_notification = function(instance, elem){
        var datedata =  moment(elem.creation_date).fromNow()
        var base = $("#temp_"+instance.attr('id')).html();
        base = base.replace('$id', elem.id).replace('$message_type', elem.message_type);
        base = base.replace('$link', elem.link).replace('$description', elem.description);
        base = base.replace('$datedata', datedata);
        base = '<li class="nitem">'+base+'</li>';
        var jbase = $(base);
        var clk = jbase.find('.clk');
        clk.on('click', this.on_click_clk(jbase, elem, this, instance))
        $("#showall_"+instance.attr('id')).before(jbase);
    }
    dropdown_actions = function(instance){
        instance.do_not_hide=false;
        $(document).on("hide.bs.dropdown", function (e) {
            if (instance.attr('id') == e.relatedTarget.id){
                if(instance.do_not_hide){
                    e.stopPropagation();
                    e.preventDefault();
                    instance.do_not_hide=false;
                }
            }
        });
    }
    set_next_prev = function(instance, data){
            if(data.next == null){
                let next = $("#next_"+instance.attr('id'));
                next.data('url', 'false');
                next.hide();
            }else{
                let next = $("#next_"+instance.attr('id'));
                next.data('url', data.next);
                next.show();
            }
            if(data.previous == null){
                let previous = $("#prev_"+instance.attr('id'));
                previous.data('url', 'false');
                previous.hide();
            }else{
                let previous = $("#prev_"+instance.attr('id'));
                previous.data('url', data.previous);
                previous.show();
            }
    }
    remove_notifications = function(instance){
        $("#ddm_"+instance.attr('id')+' .nitem').remove();
    }
    next_prev_action = function(instance){
        f = function(){
               instance.do_not_hide = true;
               var url = $(this).data('url');
               if(url != 'false'){
                    remove_notifications(instance);
                    load_notifications(instance, url);
               }
        }
        $("#prev_"+instance.attr('id')).on('click', f);
        $("#next_"+instance.attr('id')).on('click', f);

    }
    function load_notifications(instance, base_url){

        $.getJSON(base_url, function(data){
                instance.find('.notificacionnumero').text( data.count);
                for(var x=0; x<data.results.length; x++){
                    create_notification(instance, data.results[x]);
                }
                set_next_prev(instance, data);
        });

    }
    set_css_size = function(instance){
        var data = $('#ddm_'+instance.attr('id'));
        data.css({
        'max-height': $(window).height()-($(window).height()*0.2), 'overflow': 'auto'});
    }
    $.each($(this), function(i, e){
        let instance = $(e);
        let base_url = instance.data('apiurl');
        dropdown_actions(instance);
        moment.locale(instance.data('lang'));
        set_css_size(instance);
        load_notifications(instance, base_url);
        next_prev_action(instance);
    });
}