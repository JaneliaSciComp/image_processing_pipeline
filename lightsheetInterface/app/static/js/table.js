var ls_table = ls_table || {};
ls_table.loadRow = function(){
  var job_id = $(this).find('.job-id').text();
  window.location = '?lightsheetDB_id=' + job_id;
},

$(document).ready(() => {
  let table = null;
  if (table_data) {
      table = $('#job-table').DataTable({
      responsive: true,
      autoWidth: false,
      data: table_data,
      pageLength: 10,
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
        title: 'Status',
        data: 'state',
      }
      ],
    });
  }
  $('#job-table tr').click(ls_table.loadRow);
});