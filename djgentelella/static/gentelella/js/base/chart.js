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
    var reservedAttrs = ['url', 'widget'];

    var check_callbacks = function(result) {
        if (result.options && result.options.tooltips && result.options.tooltips.callbacks) {
            var cback = result.options.tooltips.callbacks;
            var callbackTypes = ['label', 'beforeLabel', 'afterLabel', 'title', 'footer'];
            callbackTypes.forEach(function(type) {
                if (cback[type] && document.chartcallbacks && document.chartcallbacks.hasOwnProperty(cback[type])) {
                    result.options.tooltips.callbacks[type] = document.chartcallbacks[cback[type]];
                }
            });
        }
        return result;
    }
    var resolveValue = function(value) {
        if (typeof value !== 'string') return value;

        if (value.startsWith('{') && value.endsWith('}')) {
            var funcName = value.slice(1, -1);
            if (typeof window[funcName] === 'function') {
                return window[funcName]();
            }
        }
        if (value.startsWith('#')) {
            var el = $(value);
            if (el.length) return el.val() || el.text();
        }
        if (value.startsWith('.')) {
            var el = $(value).first();
            if (el.length) return el.val() || el.text();
        }

        return value;
    }

    $.each($(this), function(i, e) {
        var $element = $(e);
        var url = $element.data('url');
        var canvas = $element.find('canvas');

        var params = {};
        $.each($element.data(), function(key, value) {
            if (reservedAttrs.indexOf(key) === -1) {
                params[key] = resolveValue(value);
            }
        });

        $.ajax({
            url: url,
            type: "GET",
            dataType: 'json',
            data: params,
            success: function(result) {
                var ctx = canvas[0].getContext('2d');
                var chartConfig = check_callbacks(result);
                var myChart = new Chart(ctx, chartConfig);
                $element.data('chartInstance', myChart);
            },
            error: function(xhr, resp, text) {
                console.log('Error loading chart:', text);
            }
        });
    });
}
