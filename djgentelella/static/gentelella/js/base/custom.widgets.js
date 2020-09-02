$.fn.listcrudrest = function(){
   $.each($(this), function(i, e){
    var $this=$(e),
       btn = $this.find('.additemcrudlist'),
       form = $this.find('form'),
       url_add = form.attr('action'),
       del_btn =  $this.find('.gencruddel'),
       def_url = del_btn.data('href'),
       list = $this.find('.gencrudlist');
    var template = '<li> <p><div class="icheckbox_flat-green"  >'+
       '<input type="checkbox" class="flat gencrudcheck" name="__ID__" >'+
       '<ins class="iCheck-helper" ></ins></div> __DESCRIPTION__</p></li>';


    var update_list = function(result){
        var html='';
        for(var x=0; x<result.length; x++){
            html += template.replace('__ID__', result[x].id).replace(
            '__DESCRIPTION__', result[x].name);
        }
        list.html(html);
        list.find('input').iCheck({
            checkboxClass: 'icheckbox_flat-green',
            radioClass: 'iradio_flat-green'
        });
    }
    $(btn).on('click', function(){
        $(form).closest('.x_content').find('.alert').remove();
        $.ajax({
            url: url_add, // url where to submit the request
            type : "POST", // type of action POST || GET
            dataType : 'json', // data type
            data : $(form).serialize(), // post data || get data
            success : function(result) {
                form.find('p.error').remove();
                update_list(result);
                form[0].reset();
                $(document).trigger('crudlistadd', [form, result]);
            },
            error: function(xhr, resp, text) {
                form.find('p.error').remove();
                if(xhr.status == 400 ){
                    keys = Object.keys(xhr.responseJSON)

                    $.each(keys, function(i, e){
                        var item = form.find('*[name='+e+']');
                        item.after('<p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p>');

                        if(e == 'non_field_errors'){
                            form.before('<div class="alert"><p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p></div>');
                        }

                    });
                }
            }
        });
    });

    $(del_btn).on('click', function( ){
        var todelete=[];
        $(list).find('input:checked').each(function (i,e){
            todelete.push(e.name)
        });

        $.ajax({
            url: def_url, // url where to submit the request
            type : "DELETE", // type of action POST || GET
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            dataType : 'json', // data type
            data : { 'delitems':  todelete}, // post data || get data
            success : function(result) { update_list(result); },
            error: function(xhr, resp, text) {
                console.log(xhr, resp, text);
            }
        });
    });
    });
};
$.fn.addselectwidget = function(){
    //var e=this;
    $.each(this, function(i,e){
    $(document.body).append( $($(e).data('modalname')).detach() );
    var $modalui = $($(e).data('modalname'));
    $modalui.on('show.bs.modal', function (event) {
        var modal = $(this);
        $.ajax({
            url: modal.data('url'), // url where to submit the request
            type : "GET", // type of action POST || GET
            dataType : 'json', // data type
            success : function(result) {
                modal.find('.modal-body').html(result['message']);
                modal.find('.modal-header p').html(result['title']);
                if(result.hasOwnProperty('script')){
                    eval(result['script'])
                }

            },
            error: function(xhr, resp, text) {
                console.log(xhr, resp, text);
            }
        });
    });
    $($(e).data('modalname')+' .btnsubmit').on('click', function(){
        var form = $($(e).data('modalname')+' form');
        $.ajax({
            url: $modalui.data('url'), // url where to submit the request
            type : "POST", // type of action POST || GET
            headers: {'X-CSRFToken': getCookie('csrftoken') },
            dataType : 'json', // data type
            data : $(form).serialize(), // post data || get data
            success : function(result) {
                if(result.ok){
                    var data = {
                    'id': result.id,
                    'text': result.text
                    }
                    var newOption = new Option(data.text, data.id, false, true);
                     $(e).append(newOption).trigger('change');

                    $modalui.find('.modal-body').html("");
                    $modalui.modal('hide');
                }else{
                    $modalui.find('.modal-body').html(result['message']);
                    $modalui.find('.modal-header p').html(result['title']);
                    if(result.hasOwnProperty('script')){
                       eval(result['script'])
                    }
                }
            },
            error: function(xhr, resp, text) {
                if(xhr.status == 400 ){
                    keys = Object.keys(xhr.responseJSON)

                    $.each(keys, function(i, e){
                        var item = form.find('*[name='+e+']');
                        item.after('<p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p>');
                    });
                }
            }
        });
    });
    $modalui.modal('hide');
});

}