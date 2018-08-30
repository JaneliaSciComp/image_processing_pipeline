/**
* Custom table behavior
*/
var ls_table = ls_table || {};
ls_table.loadRow = function(){
  var job_id = $(this).find('.job-id').text();
  window.location = '?lightsheetDB_id=' + job_id;
},


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
        title: 'Name',
        data: 'jobName',
        render(data, type, row, meta) {
          return data ? data : null;
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
        title: 'Steps',
        data: 'selectedSteps',
        render(data, type, row, meta) {
          names = data["names"].split(",");
          states = data["states"].split(",");
          submissionAddress = data["submissionAddress"];
          for(var i=0;i<states.length; i++){
            if(states[i]=="RUNNING"){
              names[i] = "<font color=\"blue\">" + names[i] +"</font>";
            }
            else if(states[i]=="SUCCESSFUL"){
              names[i] = "<font color=\"green\">" + names[i] +"</font>";
            }
            else if(states[i]=='RESUME' && i<states.length-1){
              names[i] = "<form action=\"/job_status?lightsheetDB_id="+row.id+"\" method=\"post\" style=\"display:inline;\"> <button> RESUME </button> </form>";
            }
            else if(states[i]=='RESET'){
              names[i] = "<form action=\""+submissionAddress+"?lightsheetDB_id="+row.id+"&reparameterize=true\" method=\"post\" style=\"display:inline;\"> <button> RESET </button> </form>";
            }
            else if(states[i]!="NOT YET QUEUED"){
              names[i] = "<font color=\"red\">" + names[i] +"</font>";
            }
          }
          names=names.join(",");
          return names ? names : null;
        },
      },
      {
       title: 'Temp',
        data: 'submissionAddress',
        render(data,type,row,meta){
          return data ? data: null
        }
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
  $('#job-table tbody tr').click(ls_table.loadRow);
});