/*
 * Custom behavior for the lightsheet landing page
*/
var dataIo = dataIo || {};

dataIo.fetch = function(url, method, data, params){
  return fetch(url, {
    method: method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  }).then(function(response) {
    if (response.status == 200) {
      return response.json();
    }
    throw new Error('Unexpected status code: ' +  response.status);
  });
};

dataIo.handleError = function(err){
  console.log(err);
};

/*
 * Grab data and submit it when pressing the button
 */
dataIo.grabData = function(){
  // Initialize object which will contain data to be posted
  var data = {};
  const jobField = $('#jobId');
  if (jobField && jobField.length > 0) {
    data['jobName'] = $('#jobId')[0].value;
  }

  //Get the checkboxes for steps, which are checked
  const checked_boxes = $('form :input[id^=check-]:checked');

  // Store values of multi-select checkboxes in corresponding input fields
  var innerFieldClass = 'filter-option-inner-inner';
  var multiCheckboxClass = 'custom-multi-checkbox';
  var checkBoxInnerFields = document.getElementsByClassName(multiCheckboxClass);

  for (var i = 0; i < checkBoxInnerFields.length; i++) {
    var selectedElements = checkBoxInnerFields[i].getElementsByClassName(innerFieldClass)[0].innerHTML;
    var outputField = checkBoxInnerFields[i].getElementsByTagName('input')[0];

    var result = '[' + selectedElements + ']';
    if (selectedElements == 'Nothing selected') {
      outputField = [];
    }
    else {
      outputField.value = result;
    }
  }

  // Submit empty values
  checked_boxes.each( function( index, element ){
    const step = this.id.replace('check-','');
    var stepType = $(this.closest('.card-header')).find('.step-type')[0];
    if (stepType) {
      stepType = stepType.innerText;
    }

    data[step] = {};

    if (stepType){
      if (stepType == 'L'){
        data[step]['type'] = 'LightSheet';
      }
      else if (stepType == 'Sp'){
        data[step]['type'] = 'Sparks';
      }
      else if (stepType == 'Si'){
        data[step]['type'] = 'Singularity';
      }
    }

    // input fields
    var inputFields = $('#collapse' + step).find('input:not([ignore])');
    const p = 'parameters';
    data[step][p] = {};

    var bindPath = [];
    inputFields.each( function(k,val) {
      if (this.hasAttribute('mount')) {
        bindPath.push(val.value);
      }
      if (!this.hasAttribute('ignore')) {
        if (this.disabled) {
          data[step][p][val.id] = '';
        }
        else {
          if (val.type== 'radio' ){
            radioButtonValue = $('#collapse' + step).find('input[name=\"'+val.name+'\"]:checked').val();
            data[step][p][val.name]  = radioButtonValue;
          }
          else if (val.type == 'checkbox') { // For checkbox parameters, only add value if it's true
            if (val.value !== undefined && val.value !== false && val.value !== 'false'){
              data[step][p][val.id] = 'True';
            }
          }
          else if (val.value) {
            data[step][p][val.id] = val.value;
          }
          else {
            data[step][p][val.id] = ''
          }
        }
      }
    });
    data[step]['bindPaths'] = bindPath.join(', ');
  });
  return data;
}

dataIo.customSubmit = function(){
    data = dataIo.grabData();
  dataIo.fetch(window.location, 'POST', data)
    .catch(dataIo.handleError);
};

dataIo.downloadSettings = async function(event,stepOrTemplateName){
  event.preventDefault();
  data = dataIo.grabData();
  var baseUrl = window.location.origin;
  dataString = JSON.stringify(data)
  var d = new Date();
  var numMilliseconds = d.getTime().toString();
  dataIo.fetch(baseUrl+'/download_settings/'+numMilliseconds+'?stepOrTemplateName='+stepOrTemplateName, 'POST', data)
    .catch(dataIo.handleError); //Post to database
  await sleep(250)//Hacky way to wait for post to finish
  window.open(baseUrl+'/download_settings/'+numMilliseconds) //Download from database 
  /*dataIo.fetch(baseUrl+'/downloadSettings/'+numMilliseconds, 'DELETE', data) //Delete from database
    .catch(dataIo.handleError);*/
  /*dataIo.fetch(baseUrl+'/downloadSettings/1539810304153', 'GET')
    .catch(dataIo.handleError);*/
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
