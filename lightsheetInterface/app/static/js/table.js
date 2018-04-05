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
        data: 'id',
        render(data, type, row, meta) {
          return data;
        }
      },
      {
        title: 'Status',
        data: 'state',
      }
      ],
    });
  }
});