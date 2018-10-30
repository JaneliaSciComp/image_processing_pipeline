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
      order: [[ 1, "desc" ]],
      responsive: true,
      autoWidth: false,
      data: table_data,
      pageLength: 25,
      columns: [{
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
              names.push("<form action=\""+baseUrl+ row.stepOrTemplateName + "?lightsheetDB_id="+row.id+"&reparameterize=true\" method=\"post\" style=\"display:inline;\"> <button> RESET </button> </form>");
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
          return data ? "<a href=\"/config/" + data +  "\">" + data + "</a>": '';
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
              jacsLinks = jacsLinks+"<a href=\"http://jacs-dev.int.janelia.org:8080/job/" + data[i] +  "\">" + data[i] + "</a>,";
            }
            jacsLinks=jacsLinks.slice(0,-1);
          }
          else{
            jacsLinks = jacsLinks+"<a href=\"http://jacs-dev.int.janelia.org:8080/job/" + data +  "\">" + data + "</a>";
          }
          return jacsLinks;
        }
      }
      ],
    });
  }
});