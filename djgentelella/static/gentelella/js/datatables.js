function formatDataTableParams(dataTableParams, settings){
    // this method will take care of clean up the default data table params sent to the backend so only
    // required info is included and is sent in the required format with the right names
    // it will be used for all data tables we will have in the system - that is why it is here

    // setup pagination and draw (param required by data tables)
    var data = {'offset': dataTableParams.start, 'limit': dataTableParams.length, 'draw': dataTableParams.draw}
    // setup global search param
    if(dataTableParams.search.value) {
        data['search'] = dataTableParams.search.value;
    }
    // setup specific field search params - strings will use icontains search, others will use exact search
    $.each(dataTableParams.columns, function(i, column){
        if(column.search.value){
             data[column.name] = column.search.value.trim();
            var column_type = settings.aoColumns[i].type;
            if(column_type === 'string') {
                data[column.name + "__icontains"] = column.search.value.trim();
            }else{
                data[column.name] = column.search.value.trim();
            }
        }
    });
    if(dataTableParams.order.length){
        // setup ordering param
        var column_name = dataTableParams.columns[dataTableParams.order[0].column].name
        var direction = dataTableParams.order[0].dir
        data['ordering'] = direction === 'desc' ? "-" + column_name : column_name;
    }
    return data;
}

function addSearchInputsAndFooterDataTable(dataTable, tableId) {
    // takes care of adding the search inputs to each of the columns of the datatable, it will
    // hide/display them according to how the table changes in the responsive mode

    if($(tableId + ' thead tr').length < 2){  // clone the tr only if it wasn't cloned before
       $(tableId + ' thead tr').clone(false).appendTo(tableId + ' thead');
    }

    $(tableId + ' thead tr:eq(1) th').each(function (i) { // add search fields if they are not there already and the column is visible
        var currentColumn = dataTable.column(i);

        var columnType = dataTable.settings()[0].aoColumns[i].type; // get the field type
        //currentColumn.responsiveHidden()
        if (currentColumn.visible() && columnType !== 'actions') {  // column is visible
            $(this).css('display', ''); // when it was cloned it might have had display:none specified
            if($(this).find('input').length === 0 && $(this).find('select').length === 0) {  // add the input/select just if it doesn't exist already
                var title = currentColumn.header().textContent;  // get the field name
                $(this).removeClass('sorting');
                $(this).removeClass('sorting_asc');
                $(this).removeClass('sorting_desc');

                if(columnType === 'boolean'){
                    $(this).html('<select class="form-control form-control-sm"><option value="">--</option><option value="True">Yes</option><option value="False">No</option></select>');
                }else if(columnType === 'date'){
                    $(this).html('<input type="text" class="form-control" autocomplete="off" placeholder="Select date" value="">');
                    var $inp = $(this).find("input");
                    var dateformat = dataTable.settings()[0].aoColumns[i].dateformat || "MM/DD/YYYY";
                    $inp.daterangepicker({showDropdowns: true, "locale": {"format": dateformat, cancelLabel: 'Clear'}});
                    $inp.val("");
                    $inp.on('cancel.daterangepicker', function(ev, picker) {
                        $inp.val("");
                        $inp.trigger('change');
                    });
                }else if(columnType == 'number'){
                    $(this).html('<input type="number" class="form-control form-control-sm" placeholder="Search ' + title + '" />');
                }else if(columnType === 'select'){
                    var choices = dataTable.settings()[0].aoColumns[i].choices;
                    var select = '<select class="form-control form-control-sm"><option value="">--</option>';
                    for(var z=0; z<choices.length; z++){
                        select += '<option value="'+choices[z][0]+'">'+choices[z][1]+'</option>';
                    }
                    select += '</select>';
                    $(this).html(select);
                }else if(columnType === 'select2'){
                    var s2url = dataTable.settings()[0].aoColumns[i].url;
                    var select = '<select class="form-control form-control-sm"><option value="">--</option>';
                    select += '</select>';
                    $(this).html(select);
                    let s2instance = $(this).find('select');
                    let s2context={
                        ajax: {  url: s2url,  dataType: 'json'}
                    }
                    extract_select2_context(s2context, s2instance);
                    s2instance.select2(s2context);
                }else if(columnType === 'readonly'){
                    $(this).html("");
                }else {
                    $(this).html('<input type="text" class="form-control form-control-sm" placeholder="Search ' + title + '" />');
                }

                $('input, select', this).on('keyup change', function () {
                    if (currentColumn.search() !== this.value) {
                        currentColumn.search(this.value).draw();
                    }
                });
            }
        }else{
            $(this).css('display', 'none');
        }

    });
    // add the footer to the table according to the current header - delete previous one before
    $(tableId).find('tfoot').remove();
    $(tableId).append($('<tfoot/>').append( $(tableId + " thead tr:eq(0)").clone()));
}

function clearDataTableFilters(dataTable, tableId){
    dataTable.search('').columns().search('').draw();
    $(tableId).find('input, select').val('');
}
function yesnoprint(data, type, row, meta){ return data ? "<i class=\"fal fa-check-circle\"></i> Yes" : "<i class=\"fal fa-times-circle\"></i> No"; };
function emptyprint(data, type, row, meta){ return data ? data : "--"; };
// hacer que se pueda definir el tipo el objeto ej data.name

function selectobjprint(config={}){
    default_display_name = config.display_name || 'display_name'
    return (data, type, row, meta)=>{
        return data ? data[default_display_name] : "---";
    }
}

function listobjprint(data, type, row, meta){
    var txt = "";
    if(data != null ){
        for(var x=0; x<data.length; x++){
            txt += data[x].display_name + "<br>"
        }
    }
    return txt != "" ? txt : "---";
};
function showlink(data, type, row, meta){ return data ? '<a href="'+data+'" target="_blank" class="btn btn-xs btn-success"> More </a>': ''; };
function downloadlink(data, type, row, meta){ return data ? '<a href="'+data+'" target="_blank" class="btn btn-xs btn-success"> Show </a>': ''; };
function objshowlink(data, type, row, meta){ return data ? '<a href="'+data.url+'" target="_blank" class="'+(data.class!=undefined ? data.class : 'link')+'"> '+data.display_name+ '</a>': ''; };
function objnode(data, type, row, meta){ return data ? '<'+data.tagName+' href="'+data.url+'" '+data.extraattr+' class="'+(data.class!=undefined ? data.class : 'link')+'"> '+data.display_name+ '</'+data.tagName+'>': ''; };

document.table_default_dom = "<'row mb-3'<'col-sm-12 col-md-4 d-flex align-items-center justify-content-start'f>" +
                 "<'col-sm-12 col-md-6 d-flex align-items-center justify-content-end'B>" +
                 "<'col-sm-12 col-md-2 d-flex align-items-center 'l>>" +
                 "<'row'<'col-sm-12'tr>><'row'<'col-sm-12 col-md-5'i><'col-sm-12 col-md-7'p>>";

function createDataTable(id, url, extraoptions={}, addfilter=false, formatDataTableParamsfnc=formatDataTableParams){
    var default_options = {
        serverSide: true,
        processing: true,
        colReorder: true,
        responsive: true,
        pagingType: "full_numbers",
        lengthMenu: [10, 25, 50, 100, 200, 500],
        columns: [
           // {data: "item_sequence", name: "item_sequence", title: "Sequence", type: "string", visible: true},
        ],
        dom: document.table_default_dom,
        buttons: [
            {
                action: function ( e, dt, node, config ) {clearDataTableFilters(dt, id)},
                text: 'Clear Filters',
                titleAttr: 'Clear Filters',
                className: 'btn-sm mr-4'
            },
        ],
        ajax: {
            url: url,
            type: 'GET',
            data: function(dataTableParams, settings) {
                return formatDataTableParamsfnc(dataTableParams, settings);
            }
        }
    }
    $.extend(default_options, extraoptions);

    var instance = $(id).DataTable(default_options);
    if(addfilter){
        instance.on('init.dt', function(e, settings, json){
            addSearchInputsAndFooterDataTable(instance, id);
        });

        instance.on('responsive-resize', function (e, datatable, columns) {
            addSearchInputsAndFooterDataTable(instance, id);
        });
    }
    return instance;
}