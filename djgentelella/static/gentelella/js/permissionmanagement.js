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



$('#permission_modal').on('show.bs.modal', function (e) {
  var urltarget = $(e.relatedTarget).data('parameter');

  $.ajax({
    url: urltarget,
    method: 'GET',
    dataType: "json"
  }).done(function(data) {
      $('#permissionbody').html(data['result']);
  });

})
})
