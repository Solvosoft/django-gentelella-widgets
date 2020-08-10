(function($){
 $.fn.relDatatables = function(){
    var url = $(this).data('rel-url');
    var parent = $(this);
    return {  datatatable: null,
              url: url,
              pk : -1,
              updateInstance : function(pk){
                 this.pk=pk;
                 this.datatatable.ajax.reload();
              },
              initialize: function(extras={}){
                  var params = $.extend({
                        serverSide: true,
                        processing: true,
                        colReorder: true,
                        responsive: true,
                        pagingType: "full_numbers",
                         "ajax": {
                            url: this.url,
                            data: this.formatDataTableParams(this)
                         },

                   }, extras);
                  this.datatatable = parent.DataTable(params);
              },
              formatDataTableParams: function(parent){
                return function(dataTableParams, settings){
                    // this method will take care of clean up the default data table params sent to the backend so only
                    // required info is included and is sent in the required format with the right names
                    // it will be used for all data tables we will have in the system - that is why it is here

                    // setup pagination and draw (param required by data tables)
                    var data = {'offset': dataTableParams.start, 'limit': dataTableParams.length,
                    'draw': dataTableParams.draw, relinst: parent.pk}
                    // setup global search param
                    if(dataTableParams.search.value) {
                        data['search'] = dataTableParams.search.value;
                    }

                    // setup specific field search params - strings will use icontains search, others will use exact search
                    $.each(dataTableParams.columns, function(i, column){
                        if(column.search.value){
                            var column_type = settings.aoColumns[i].type;
                            if(column_type === 'string') {
                                data[column.name + "__icontains"] = column.search.value.trim();
                            }else{
                                data[column.name] = column.search.value.trim();
                            }
                        }
                    });
                    // setup ordering param
                    var column_name = dataTableParams.columns[dataTableParams.order[0].column].name
                    var direction = dataTableParams.order[0].dir
                    data['ordering'] = direction === 'desc' ? "-" + column_name : column_name;
                    return data;
                }},
              };
 }

})(jQuery)
