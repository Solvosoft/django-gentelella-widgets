          $(document).ready(function(){
              $('#select_user').select2({
                  ajax: {
                    url: permission_context.select_user_url,
                    dataType: 'json',
                  },
                  width: '100%',
                  placeholder:   permission_context.user_placeholder ,
              });
              $('#select_group').select2({
                  ajax: {
                    url: permission_context.select_group_url,
                    dataType: 'json',
                  },
                  width: '100%',
                  placeholder: permission_context.group_placeholder,
              });
              $('.btn-toggle').click(function() {
                $(this).find('.btn').toggleClass('active');
                if ($(this).find('.btn-primary').size()>0) {
                  $(this).find('.btn').toggleClass('btn-primary');
                }
                $(this).find('.btn').toggleClass('btn-default');
              });
              $("#group_container").hide();
              $('#btn_user').click(function(){
                  $("#user_container").show();
                  $("#group_container").hide();
              });
              $("#btn_group").click(function(){
                $("#group_container").show();
                $("#user_container").hide();
              })


function addevent_check_permission(){

    Array.from($('input[type="checkbox"][name="permission"]')).forEach(function(checkbox){

        checkbox.addEventListener('click', function() {

            if($(this).parent().hasClass('checked')){
                $(this).parent().removeClass('checked');
            }else{
                $(this).parent().addClass('checked');
            }

        });
    });

}

function update_categorieicon_collapsed(){

    Array.from($('a.categories')).forEach(function(categorie){

        categorie.addEventListener('click', function() {

            var icon = null;

            if($(this).children()){
                icon = $(this).children()[0];
            }

             if($($(this).data('target')).is(":visible") == true){
                if(icon){
                    $(icon).removeClass('fa fa-minus');
                    $(icon).addClass('fa fa-plus');
                }
            }else{
                if(icon){
                    $(icon).removeClass('fa fa-plus');
                    $(icon).addClass('fa fa-minus');
                }
            }

        });
    });

}


    $('#permission_modal').on('show.bs.modal', function (e) {
      var urltarget = $(e.relatedTarget).data('parameter');

      $.ajax({
        url: urltarget,
        method: 'GET',
        dataType: "json"
      }).done(function(data) {
          $('#permissionbody').html(data['result']);
          addevent_check_permission();
          update_categorieicon_collapsed();
    })

    });

});