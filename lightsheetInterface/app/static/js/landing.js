/*
 * Custom behavior for the lightsheet landing page
*/
var lightsheet = lightsheet || {};

lightsheet.filterTable = function() {
  var input, filter, table, tr, td, i;
  var input = document.getElementById("search-input");
  var filter = input.value.toUpperCase();
  var table = document.getElementById("job-table-body");
  var tr = table.getElementsByTagName("tr");
  var found = null;
  for (var i = 0; i < tr.length; i++) {
    var td = tr[i].getElementsByTagName("td");
    found = false;
    if (td) {
      for (var j = 0; j < td.length; j++) {
        if (td[j].innerHTML.toUpperCase().indexOf(filter) > -1) {
          found = true;
          break;
        }
      }
    }
    if (found) {
      tr[i].style.display = "";
    }
    else {
      tr[i].style.display = "none";
    }
  }
}

lightsheet.sortTable = function(n) {
   var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
  table = document.getElementById("job-table");
  switching = true;
  //Set the sorting direction to ascending:
  dir = "asc";
  /*Make a loop that will continue until
  no switching has been done:*/
  while (switching) {
    //start by saying: no switching is done:
    switching = false;
    rows = table.getElementsByTagName("TR");
    /*Loop through all table rows (except the
    first, which contains table headers):*/
    for (i = 1; i < (rows.length - 1); i++) {
      //start by saying there should be no switching:
      shouldSwitch = false;
      /*Get the two elements you want to compare,
      one from current row and one from the next:*/
      x = rows[i].getElementsByTagName("TD")[n];
      y = rows[i + 1].getElementsByTagName("TD")[n];
      /*check if the two rows should switch place,
      based on the direction, asc or desc:*/
      if (dir == "asc") {
        if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
          //if so, mark as a switch and break the loop:
          shouldSwitch= true;
          break;
        }
      } else if (dir == "desc") {
        if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) {
          //if so, mark as a switch and break the loop:
          shouldSwitch= true;
          break;
        }
      }
    }
    if (shouldSwitch) {
      /*If a switch has been marked, make the switch
      and mark that a switch has been done:*/
      rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
      switching = true;
      //Each time a switch is done, increase this count by 1:
      switchcount ++;
    } else {
      /*If no switching has been done AND the direction is "asc",
      set the direction to "desc" and run the while loop again.*/
      if (switchcount == 0 && dir == "asc") {
        dir = "desc";
        switching = true;
      }
    }
  }
}

lightsheet.stepsExistingJob = function(){
  var checkedBoxes = $('.step-checkbox:checked');
  $.each(checkedBoxes, function(obj) {
    var name = $(this)[0].id.split('-')[1];
    if (name) {
      $('#' + 'collapse' + name).addClass('show');
    }
  });
}