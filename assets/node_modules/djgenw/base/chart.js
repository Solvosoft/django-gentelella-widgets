document.chartcallbacks = {
   doughnutlabels: function (item, data) {

        var label = data.datasets[item.datasetIndex].label;
        var value = data.datasets[item.datasetIndex].data[item.index];
        return label + ': ' + value;
    },
   doughnutbeforeLabel: function(tooltipItem, chart){
        return chart.datasets[tooltipItem.datasetIndex]['label']
    }
}
$.fn.gentelella_chart = function(){

   check_callbacks=function(result){
        if(result.options && result.options.tooltips && result.options.tooltips.callbacks){
           var cback = result.options.tooltips.callbacks;
           if(cback.label){
                if(document.chartcallbacks.hasOwnProperty(cback.label)){
                    result.options.tooltips.callbacks.label = document.chartcallbacks[cback.label]
                }
           }
          if(cback.beforeLabel){
                if(document.chartcallbacks.hasOwnProperty(cback.beforeLabel)){
                    result.options.tooltips.callbacks.beforeLabel = document.chartcallbacks[cback.beforeLabel]
                }
          }
        }
       return result
   }

   $.each($(this), function(i, e){
    var url = $(e).data('url');
    var canvas = $(e).find('canvas');
    $.ajax({
        url: url,
        type : "GET",
        dataType : 'json',
        success : function(result) {
           var ctx = canvas[0].getContext('2d');
           var myChart = new Chart(ctx, check_callbacks(result));

        },
        error: function(xhr, resp, text) {
           console.log(text);
        }
    });
   });
}