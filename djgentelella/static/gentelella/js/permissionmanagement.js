selected_user_or_group = false;
option = 0;
get_permissions = "";
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
        selected_user_or_group = false;
        $("#user_container").show();
        $("#group_container").hide();
        var checkboxes = $('input[type="checkbox"][name="permission"]');
        checkboxchecked = checkboxes.filter(':checked');
        checkboxchecked.iCheck('uncheck');
        $("#select_user").empty().trigger('change')
        $("#select_group").empty().trigger('change')
        option = 0
    });

    $("#btn_group").click(function(){
        $("#group_container").show();
        selected_user_or_group = false;
        $("#user_container").hide();
        var checkboxes = $('input[type="checkbox"][name="permission"]');
        checkboxchecked = checkboxes.filter(':checked');
        checkboxchecked.iCheck('uncheck');
        $("#select_user").empty().trigger('change')
        $("#select_group").empty().trigger('change')
        option = 2
    });


    $('#select_user').on('select2:select', function (evt) {
      selected_user_or_group = true;
      url = permission_context.get_permissions.replace(/\/(\d+)$/, "/"+evt.params.data.id)
      permission_context.get_permissions = url
      get_permissions_url = permission_context.get_permissions+"?option="+option+"&q="+$('#btn_perms').data("urlname");
      $.ajax({
        url: get_permissions_url,
        method: 'GET',
        dataType: "json",
        success: function(data){
          var checkboxes = $('input[type="checkbox"][name="permission"]');
          if(data['result'].length>0){
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
            data['result'].forEach(function(i){
              console.log(i)
              $('input[type="checkbox"][value="'+i.id+'"]').iCheck('check');
            });
          }else{
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
          }
        },
        error: function(xhr, ajaxOptions, thrownError){
          if(xhr.status==404) {
            //Do something here
          }
        }
      });
    });

    $('#select_group').on('select2:select', function (evt) {
      selected_user_or_group = true;
      url = permission_context.get_permissions.replace(/\/(\d+)$/, "/"+evt.params.data.id)
      permission_context.get_permissions = url
      get_permissions_url = permission_context.get_permissions+"?option="+option+"&q="+$('#btn_perms').data("urlname");
      $.ajax({
        url: get_permissions_url,
        method: 'GET',
        dataType: "json",
        success: function(data){
          var checkboxes = $('input[type="checkbox"][name="permission"]');
          if(data['result'].length>0){
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
            data['result'].forEach(function(i){
              console.log(i)
              $('input[type="checkbox"][value="'+i.id+'"]').iCheck('check');
            });
          }else{
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
          }
        },
        error: function(xhr, ajaxOptions, thrownError){
          if(xhr.status==404) {
            //Do something here
          }
        }
      });
    });

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
        dataType: "json",
        success: function(data){
          result = data['result'];
          if (result == "" ){
            result = permission_context.not_found_permissions_label;
          }
          $('#permissionbody').html(result);
          $('input[type="checkbox"][name="permission"]').iCheck({
            checkboxClass: 'icheckbox_flat-green',
            radioClass: 'iradio_flat-green',
            increaseArea: '20%' // optional
          });
          update_categorieicon_collapsed();
        },
        error: function(xhr, ajaxOptions, thrownError){
          if(xhr.status==404) {
            $('#permissionbody').html(permission_context.not_found_permissions_label);
          }
        }
      });

    });

  $("#btn_savepermissions").click(function(){
    if(selected_user_or_group){
      Swal.fire({
        position: 'top-end',
        icon: 'success',
        title: 'Your work has been saved',
        showConfirmButton: false,
        timer: 3000,
      });
    }else{
      Swal.fire({
        position: 'top-end',
        icon: 'error',
        title: 'Error al guardar',
        text: 'No ha seleccionado una opción valida',
        timer: 3000,
      });
    }
  })

});