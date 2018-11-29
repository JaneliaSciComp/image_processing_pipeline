/*
 * Custom behavior for the lightsheet landing page
*/
var lightsheet = lightsheet || {};

/*
 * Check, if there is a step checkbox checked, if not, disable submit button
*/
lightsheet.testAllCheckboxes = function(object){
  if(object && !object.checked ){//minimize if unchecked
      stepName = object.id.split("-")[1];
      expandIcon = document.getElementById("expandIcon-"+stepName);
      if (expandIcon.innerHTML == "▾") {
          expandIcon.click();
      }
  }
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

lightsheet.expandStep = function(object){
  stepName = object.id.split("-")[1];
  if(object.innerHTML=="▸") {
      object.innerHTML = "▾";
      document.getElementById("check-"+stepName).checked=true;
      lightsheet.testAllCheckboxes();
  }
  else{
    object.innerHTML="▸";
  }
};

lightsheet.toggleHideButton = function(){
  hideCheckboxes = document.querySelectorAll("[id*='hideCheckbox_']");
  disableHideButton = true;
  for(var i=0; i< hideCheckboxes.length; i++){
        if (hideCheckboxes[i].checked){
          disableHideButton = false;
          break;
        }
  }
  hideButton = document.getElementById("hideEntries");
  hideButton.disabled = disableHideButton;
};

lightsheet.hideEntries = function(){
  var result= confirm('Are you sure you would like to hide in display? (Note: This will not delete from the database)');
  if(result) {
      hideCheckboxes = document.querySelectorAll("[id*='hideCheckbox_']");
      job_ids_to_hide=[];
      for(var i=0; i< hideCheckboxes.length; i++){
          //Get ids to hide and
          if (hideCheckboxes[i].checked) {
              id = hideCheckboxes[i].id;
              splitted = id.split("_");
              job_id = splitted[1];
              job_ids_to_hide.push(job_id)
          }
      }
      var baseUrl = window.location.origin;
      dataIo.fetch(baseUrl+'/hide_entries/', 'POST', job_ids_to_hide);
      $('#job-table').DataTable().ajax.reload(null, false);
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