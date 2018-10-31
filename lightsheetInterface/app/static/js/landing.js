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
    $('.submit-button').each(function(){
      this.disabled = false;
    });
  }
  else {
    $('.submit-button').each(function(){
      this.disabled = true;
    });
  }
};

lightsheet.toggleDeleteButton = function(){
  deleteCheckboxes = document.querySelectorAll("[id*='deleteCheckbox_']");
  disableDeleteButton = true;
  for(var i=0; i< deleteCheckboxes.length; i++){
        if (deleteCheckboxes[i].checked){
          disableDeleteButton = false;
          break;
        }
  }
  deleteButton = document.getElementById("deleteEntries");
  deleteButton.disabled = disableDeleteButton;
};

lightsheet.deleteEntries = function(){
  var result= confirm('Are you sure you would like to delete from the database?');
  if(result) {
      deleteCheckboxes = document.querySelectorAll("[id*='deleteCheckbox_']");
      job_ids_to_delete=[];
      for(var i=0; i< deleteCheckboxes.length; i++){
          //Get ids to delete and
          if (deleteCheckboxes[i].checked) {
              id = deleteCheckboxes[i].id;
              splitted = id.split("_");
              job_id = splitted[1];
              job_ids_to_delete.push(job_id)
          }
      }
      var baseUrl = window.location.origin;
      dataIo.fetch(baseUrl+'/delete_entries/', 'POST', job_ids_to_delete)
      var urlParams = new URLSearchParams(window.location.search)
      if (job_ids_to_delete.indexOf(urlParams.get('lightsheetDB_id'))>=0) {//Then it was deleted and we need to reload an earlier verison of the page
          replaceURL = window.location.href.split('?')[0];
      }
      else {
        replaceURL = window.location.href;
      }
      window.location.replace(replaceURL)
  }
}
/*
 * Do checkbox test once when loading the page
*/
lightsheet.testCheckboxes = (function(){
  lightsheet.testAllCheckboxes();
})();


/*
 * For paramters which have afirst and a second value, convert them to an array (TODO: also check if they are a range parameter)
 */
lightsheet.buildParameterObject = function(fieldObject) {
  // Check if the id of the fieldObject has a hyphen in there:
  var fieldName = fieldObject.id;
  // save paramter values into one global

  if (lightsheet.dictParameters !== null) {
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
};


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
};

// Expand tabs for checkbox checked
lightsheet.stepsExistingJob = function(){
  var checkedBoxes = $('.step-checkbox:checked');
  $.each(checkedBoxes, function(obj) {
    var name = $(this)[0].id.split('-')[1];
    if (name) {
      $('#' + 'collapse' + name).addClass('show');
    }
  });
};

// Disable input fields, when checkbox is checked, that those fields should be ignored
lightsheet.passEmptyField = function(obj){
  var inputs = obj.parentNode.parentNode.getElementsByTagName('input');
  for (var i=0; i< inputs.length-1; i++){
      if (obj.checked){
        inputs[i].disabled=false;
        inputs[i].click();
        inputs[i].disabled = true;
        obj.value= true;
      }
      else{
        inputs[i].disabled = false;
        inputs[i].click();
        obj.value = false;
      }
  }
};

$(document).ready(function(){
  $('#pipeline-configs').on('change', function(event){
    var pipeline_name = $(this).find(":selected").val();
    window.location = window.origin + '/load/' + pipeline_name;
  });
});