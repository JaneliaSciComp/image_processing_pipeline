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
      },
      {
        title: 'Date',
        data: 'creationDate',
        render(data, type, row, meta) {
          return data? data: null;
        }
      },
      {
        title: 'Steps',
        data: 'selectedStepNames',
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
      },
      {
        title: 'Jacs ID',
        data: 'jacs_id',
        render(data, type, row, meta) {
          return "<a href=\"http://jacs-dev.int.janelia.org:8080/job/" + data +  "\">" + data + "</a>";
        }
      }
      ],
    });
  }
  $('#job-table tbody tr').click(ls_table.loadRow);
});