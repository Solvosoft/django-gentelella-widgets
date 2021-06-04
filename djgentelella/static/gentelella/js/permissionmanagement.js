selected_user_or_group = false;
option = 1;
get_permissions = "";
group_id = 0;
user_id = 0;

const Toast = Swal.mixin({
  toast: true,
  position: 'top-end',
  showConfirmButton: false,
  timer: 3000,
  timerProgressBar: true,
  didOpen: (toast) => {
    toast.addEventListener('mouseenter', Swal.stopTimer)
    toast.addEventListener('mouseleave', Swal.resumeTimer)
  }
});

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
        option = 1
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
      user_id = evt.params.data.id
      url = permission_context.get_permissions.replace("/0", "/"+user_id)
      get_permissions_url = url+"?option="+option+"&urlname="+encodeURIComponent($('#btn_perms').data("urlname"));
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
      group_id = evt.params.data.id
      url = permission_context.get_permissions.replace("/0", "/"+group_id)
      get_permissions_url = url+"?option="+option+"&urlname="+encodeURIComponent($('#btn_perms').data("urlname"));
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

    if($('#btn_perms').data("urlname")!=""){
      if(selected_user_or_group){
        permsurl_save = permission_context.save_permissions
        selected = []
        inputs_selected = $('input[type="checkbox"][name="permission"]').filter(":checked");
        for(i=0; i < inputs_selected.length; i++){
          selected.push($(inputs_selected[i]).val());
        }
        data_save = {
          "option": option,
          "permissions": selected,
          "urlname": $('#btn_perms').data("urlname"),
        };
        if(option == 2){
          data_save['group'] = group_id;
        }else{
          data_save['user'] = user_id;
        }

        $.ajax({
          url: permsurl_save,
          method: "POST",
          dataType: "json",
          data: data_save,
          traditional: true,
          headers: {'X-CSRFToken': getCookie('csrftoken') },
          success: function(data){

            var checkboxes = $('input[type="checkbox"][name="permission"]');
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
            $("#select_user").empty().trigger('change')
            $("#select_group").empty().trigger('change')
            Toast.fire({
              icon: 'success',
              title: permission_context.save_messages
            });
             selected_user_or_group = false;
             $('#permission_modal').modal('hide');
          },
          error: function(xhr, ajaxOptions, thrownError){

            Toast.fire({
                icon: 'error',
                title: permission_context.error
            });
          }
        });      
      }else{

        Toast.fire({
            icon: 'error',
            title: permission_context.not_select_valid_option
        });
      }
    }else{
      Toast.fire({
          icon: 'error',
          title: permission_context.not_found_permissions_label
      });
    }
    });

});