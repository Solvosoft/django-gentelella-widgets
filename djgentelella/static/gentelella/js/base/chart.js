// Tooltip callbacks cannot travel as JSON, so the server sends the name of one
// of these and the browser looks it up. Chart.js 3 replaced the v2
// `(item, data)` pair with a single tooltip context object.
document.chartcallbacks = {
   doughnutlabels: function (context) {
        return context.dataset.label + ': ' + context.parsed;
    },
   doughnutbeforeLabel: function (context) {
        return context.dataset.label;
    }
}
$.fn.gentelella_chart = function(){
    var reservedAttrs = ['url', 'widget'];

    var check_callbacks = function(result) {
        // options.tooltips became options.plugins.tooltip in Chart.js 3.
        var tooltip = result.options && result.options.plugins &&
            result.options.plugins.tooltip;
        if (tooltip && tooltip.callbacks) {
            var cback = tooltip.callbacks;
            var callbackTypes = ['label', 'beforeLabel', 'afterLabel', 'title', 'footer'];
            callbackTypes.forEach(function(type) {
                if (cback[type] && document.chartcallbacks && document.chartcallbacks.hasOwnProperty(cback[type])) {
                    cback[type] = document.chartcallbacks[cback[type]];
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
