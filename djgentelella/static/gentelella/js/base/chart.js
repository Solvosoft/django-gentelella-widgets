$.fn.gentelella_chart = function(){
   $.each($(this), function(i, e){
    var url = $(e).data('url');
    var canvas = $(e).find('canvas');
    $.ajax({
        url: url,
        type : "GET",
        dataType : 'json',
        success : function(result) {
           var ctx = canvas[0].getContext('2d');
           var myChart = new Chart(ctx, result);

        },
        error: function(xhr, resp, text) {
           console.log(text);
        }
    });
   });
}