/**
 * Custom table behavior
 */

/**
 * Generate jQuery datatables table
 */

$(document).ready(()=>{let table=null;
    var jacs_dashboard = "{{ jacs_dashboard }}";
    table = $('#job-table').DataTable({
        stateSave:false,
        order: [[3, "desc"]],
        responsive: true,
        autoWidth: false,
        ajax: tableDataURL,
        pageLength: 25,
        columnDefs: [{visible: false, targets: hideColumns}],
        columns: [
            {
                title: 'Hide',
                data: 'id',
                render: function (data, type, row) {
                        return '<input type="checkbox" id = hideCheckbox_' + data + ' class="editor-active" onclick="lightsheet.toggleHideButton()">';
                },
                className: "dt-body-center"
            },
            {
                title: 'User Name',
                data: 'username',
                render: function (data, type, row) {
                    return data ? data : null;
                },
            },
            {
                title: 'Name (Click To Load)',
                data: 'jobName',
                render(data, type, row, meta) {
                    var baseUrl = window.location.origin
                    return data ? "<a href=\"" + baseUrl + row.stepOrTemplateName + "?lightsheetDB_id=" + row.id + "\">" + data + "</a>" : '';
                }
            },
            {
                title: 'Date',
                data: 'creationDate',
                render(data, type, row, meta) {
                    return data ? data : null;
                }
            },
            {
                title: 'Job Type',
                data: 'jobType',
                render(data, type, row, meta) {
                    return data ? data : null;
                }
            },
            {
                title: 'Steps',
                data: 'selectedSteps',
                render(data, type, row, meta) {
                    namesProvided = data["names"].split(",");
                    states = data["states"].split(",");
                    names = []; //Need this because we have states include RESET/RESUME which means there are more states than step names
                    namesIndex = 0;
                    for (var i = 0; i < states.length; i++) {
                        if (states[i] == "RUNNING") {
                            names.push("<font color=\"blue\">" + namesProvided[namesIndex] + "</font>");
                            namesIndex++;
                        }
                        else if (states[i] == "SUCCESSFUL") {
                            names.push("<font color=\"green\">" + namesProvided[namesIndex] + "</font>");
                            namesIndex++;
                        }
                        else if (states[i] == 'RESUME' && i < states.length - 1) {
                            if (!allJobs) {
                                names.push("<form action=\"/job_status?lightsheetDB_id=" + row.id + "\" method=\"post\" style=\"display:inline;\"> <button> RESUME </button> </form>");
                            }
                        }
                        else if (states[i] == 'RESET') {
                            if (!allJobs) {
                                var baseUrl = window.location.origin;
                                names.push("<button onclick=\"dataIo.reset('" + row.stepOrTemplateName + "','" + row.id + "')\"> RESET </button> ");
                            }
                        }
                        else if (states[i] == "NOT YET QUEUED" || states[i] == "CREATED" || states[i] == "DISPATCHED") {
                            names.push("<font>" + namesProvided[namesIndex] + "</font>");
                            namesIndex++;
                        }
                        else {
                            names.push("<font color=\"red\">" + namesProvided[namesIndex] + "</font>");
                            namesIndex++;
                        }
                    }
                    names = names.join(",");
                    return names ? names : null;
                },
            },
            {
                title: 'Job ID (and Configuration Link)',
                className: 'job-id',
                data: 'id',
                render(data, type, row, meta) {
                    return data ? "<a href=\"/config/" + data + "\" target=\"_blank\">" + data + "</a>" : '';
                }
            },
            {
                title: 'State',
                data: 'state',
                render(data, type, row, meta) {
                    return data ? data : null;
                }
            },
            {
                title: 'Jacs ID',
                data: 'jacs_id',
                render(data, type, row, meta) {
                    var jacsLinks = "";
                    if (data && data.constructor === Array) {
                        for (var i = 0; i < data.length; i++) {
                            jacsLinks = jacsLinks + "<a href=\"" + jacs_dashboard + "/job/" + data[i] + "\" target=\"_blank\">" + data[i] + "</a>,";
                        }
                        jacsLinks = jacsLinks.slice(0, -1);
                    }
                    else {
                        jacsLinks = jacsLinks + "<a href=\"" + jacs_dashboard + "/job/" + data + "\" target=\"_blank\">" + data + "</a>";
                    }
                    return jacsLinks;
                }
            }
        ],
    });
    var previousOrder=table.order().concat();
    setInterval(function(){
        //check if any hides are checked, in which case wait to refresh table
        if ($('input:checkbox[id^="hideCheckbox_"]:checked').length==0){
            //to prevent resorting that undoes previous sorting, need to keep current order and append the previous order
            currentOrder = table.order().concat();
            var  order = currentOrder.concat();
            for (var i=0; i<previousOrder.length; i++){
                appendToOrder=true;
                for(var j=0; j<currentOrder.length; j++) {
                    if (previousOrder[i][0] == currentOrder[j][0]) {//then referencing same column and only want to take that referring to differentOne
                        appendToOrder = false;
                        break;
                    }
                }
                if(appendToOrder){
                    order.push(previousOrder[i])
                }
            }
            previousOrder=order.concat();
            table.order(order);
            table.ajax.reload(null, false);
        }
    }, 30000);

})
;