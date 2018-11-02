/**
* Custom table behavior
*/

/**
* Generate jQuery datatables table
*/

$(document).ready(() => {
  let table = null;
  if (table_data) {
      table = $('#job-table').DataTable({
      order: [[ 2, "desc" ]],
      responsive: true,
      autoWidth: false,
      data: table_data,
      pageLength: 25,
      columns: [
      { title: 'Delete',
        data:   'id',
        render: function ( data, type, row ) {
          if ( type === 'display' ) {
              return '<input type="checkbox" id = deleteCheckbox_' + data + ' class="editor-active" onclick="lightsheet.toggleDeleteButton()">';
          }
          return data;
      },
      className: "dt-body-center"
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
          for(var i=0;i<states.length; i++){
            if(states[i]=="RUNNING"){
              names.push("<font color=\"blue\">" + namesProvided[namesIndex] +"</font>");
              namesIndex++;
            }
            else if(states[i]=="SUCCESSFUL"){
              names.push("<font color=\"green\">" + namesProvided[namesIndex] +"</font>");
              namesIndex++;
            }
            else if(states[i]=='RESUME' && i<states.length-1){
              names.push("<form action=\"/job_status?lightsheetDB_id="+row.id+"\" method=\"post\" style=\"display:inline;\"> <button> RESUME </button> </form>");
            }
            else if(states[i]=='RESET'){
              var baseUrl = window.location.origin;
              names.push("<button onclick=\"dataIo.reset('"+row.stepOrTemplateName+ "','"+ row.id+"')\"> RESET </button> ");
            }
            else if(states[i]=="NOT YET QUEUED" || states[i]=="CREATED"){
              names.push("<font>" + namesProvided[namesIndex] +"</font>");
              namesIndex++;
            }
            else{
              names.push("<font color=\"red\">" + namesProvided[namesIndex] +"</font>");
              namesIndex++;
            }
          }
          names=names.join(",");
          return names ? names : null;
        },
      },
      {
        title: 'Job ID (and Configuration Link)',
        className: 'job-id',
        data: 'id',
        render(data, type, row, meta) {
          return data ? "<a href=\"/config/" + data +  "\" target=\"_blank\">" + data + "</a>": '';
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
          var jacsLinks="";
          if(data && data.constructor === Array){
            for(var i=0; i<data.length; i++){
              jacsLinks = jacsLinks+"<a href=\"http://jacs-dev.int.janelia.org:8080/job/" + data[i] +  "\" target=\"_blank\">" + data[i] + "</a>,";
            }
            jacsLinks=jacsLinks.slice(0,-1);
          }
          else{
            jacsLinks = jacsLinks+"<a href=\"http://jacs-dev.int.janelia.org:8080/job/" + data +  "\" target=\"_blank\">" + data + "</a>";
          }
          return jacsLinks;
        }
      }
      ],
    });
  }
});