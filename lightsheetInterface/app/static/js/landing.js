/*
 * Custom behavior for the lightsheet landing page
*/
var lightsheet = lightsheet || {};

/*
 * Check, if there is a step checkbox checked, if not, disable submit button
*/
lightsheet.testAllCheckboxes = function(){
  const checked_boxes = $('form :input[id^=check-]:checked');
  if (checked_boxes.length > 0) {
    $('#submit-button')[0].disabled = false;
  }
  else {
    $('#submit-button')[0].disabled = true;
  }
}

/*
 * Do checkbox test once when loading the page
*/
lightsheet.testCheckboxes = (function(){
  lightsheet.testAllCheckboxes()
})();

/*
 * Grab data and submit it when pressing the button
 */
lightsheet.customSubmit = function(){
  const url = window.origin;
  const formInput = $('form :input');

  // Initialize object which will contain data to be posted
  var data = {}

  const jobField = $('#jobId');
  let job_name = null;
  if (jobField && jobField.length > 0) {
    data['jobName'] = $('#jobId')[0].value;
  }

  //Get the checkboxes, which are checked
  const checked_boxes = $('form :input[id^=check-]:checked');
  checked_boxes.each( function( index, element ){
    const step = this.id.replace('check-','');
    data[step] = {}
    var inputFields = $('#collapse' + step).find('input');
    inputFields.each( function(k,val) {
      data[step][val.id] = val.value;
      })
    });

  const formDataRequest = new Request(url, { method: 'POST' });
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  }).then(function(response) {
      return response.json();
  }).then(function(data) {
    console.log('error in fetch');
  });
}


/*
 * For paramters which have afirst and a second value, convert them to an array (TODO: also check if they are a range parameter)
 */
lightsheet.buildParameterObject = function(fieldObject) {
  // Check if the id of the fieldObject has a hyphen in there:
  var fieldName = fieldObject.id;
  // get just the first part, if the parameter name contains a hyphen
  var coreName = fieldName.split('-')[0]
  // save paramter values into one global

  if (lightsheet.dictParameters !== null) {
    console.log(lightsheet.dictParameters);
    var fields = Object.keys(lightsheet.dictParameters);

    if (fields.indexOf(fieldName) !== -1) { // field already there
      lightsheet.dictParameters[fieldName].push(fieldObject.value);
    }
    else { // create the list first
      lightsheet.dictParameters[fieldName] = [];
      lightsheet.dictParameters[fieldName].push(fieldObject.value);
    }
  }
  else {
    lightsheet.dictParameters = {};
    lightsheet.dictParameters[fieldName] = [];
    lightsheet.dictParameters[fieldName].push(fieldObject.value);
  }
}


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

// Expand tabs for checkbox checked
lightsheet.stepsExistingJob = function(){
  var checkedBoxes = $('.step-checkbox:checked');
  $.each(checkedBoxes, function(obj) {
    var name = $(this)[0].id.split('-')[1];
    if (name) {
      $('#' + 'collapse' + name).addClass('show');
    }
  });
}

// use template entries from model to apply global parameters
lightsheet.applyGlobalParameter = function(){
  if (templateObj) {
    for (var t = 0; t < templateObj.length; t++) {
      var output = Mustache.render("input {{ input }}, who is {{ output }} years old", templateObj[0]);
      console.log(output);
    }
  }
}