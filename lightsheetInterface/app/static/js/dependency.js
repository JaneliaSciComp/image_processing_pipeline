/*
 * Custom behavior for the lightsheet landing page
*/
var dependency = dependency || {};

// use template entries from model to apply global parameters
dependency.applyGlobalParameter = function(){
  if (value_dependencies) {
    for (var t = 0; t < value_dependencies.length; t++) {
      var globalId = Mustache.render("globalParameters-{{input}}", value_dependencies[t]);
      var stepId = Mustache.render("{{step}}-{{output}}", value_dependencies[t]);
      var globalElem = document.getElementById(globalId);
      var stepElem = document.getElementById(stepId);
      if (value_dependencies[t].pattern) {
        // Do something with the given pattern
        var pattern=value_dependencies[t].pattern;
        var variables = pattern.match(/[^\{\]]+(?=\})/g);
        for (var i=0; i<variables.length; i++){
          var currentVariableId;
          currentVariableId = "globalParameters-"+variables[i];
          needToFormat=false;
          if (currentVariableId.includes("_string")){
            needToFormat=true;
            currentVariableId=currentVariableId.replace("_string","");
          }
          if (currentVariableId.includes("cameras") || currentVariableId.includes("channels")){
            currentVariableValue = getCheckboxVal(currentVariableId);
          }
          else{
            var globalElem = document.getElementById(currentVariableId);
            var globalInputs = globalElem.getElementsByTagName('input');
            var currentVariableValue = globalInputs[0].value;
          }
          if(needToFormat){
            var prefix;
            if (currentVariableId.includes("specimen")){
              prefix="SPM";
              iterations = 1; //need this because this is a string and don't want to iterate through each character
            }
            else if (currentVariableId.includes("cameras")){
              prefix="CM";
              iterations = currentVariableValue.length;
            }
            else if (currentVariableId.includes("channels")){
              prefix="CHN";
              iterations=currentVariableValue.length;
            }
            var currentVariableValueFormatted="";
            for(var j=0; j<iterations;j++){
              currentVariableValueFormatted = currentVariableValueFormatted + (prefix+"0"+currentVariableValue[j].replace(".0","")+"_");
            }
            currentVariableValue = currentVariableValueFormatted.slice(0,-1); //Remove trailing "_"
          }
          pattern = pattern.replace("{"+variables[i]+"}",currentVariableValue);
        }
        pattern = pattern.replace("//","/");
        var stepInputs = stepElem.getElementsByTagName('input');
        stepInputs[0].value = pattern;
      }
      else {
        // We're dealing with array or range parameters
        if (globalElem && stepElem) {
          var globalInputs = globalElem.getElementsByTagName('input');
          var stepInputs = stepElem.getElementsByTagName('input');
          var gObj = {};
          var sObj = {};
          if (value_dependencies[t].formatting == 'R') {
            var tGlobalStart = Mustache.render("{{input}}-start", value_dependencies[t]);
            var tGlobalEnd = Mustache.render("{{input}}-end", value_dependencies[t]);
            var tGlobalEvery = Mustache.render("{{input}}-every", value_dependencies[t]);
            for (var i = 0; i < globalInputs.length; i++) {
              switch(globalInputs[i].getAttribute('id')) {
                case tGlobalStart:
                  gObj['start'] = globalInputs[i].value;
                  break;
                case tGlobalEnd:
                  gObj['end'] = globalInputs[i].value;
                  break;
                case tGlobalEvery:
                  gObj['every'] = globalInputs[i].value;
                  break;
              }
            }
            var tStepStart = Mustache.render("{{output}}-start", value_dependencies[t]);
            var tStepEnd = Mustache.render("{{output}}-end", value_dependencies[t]);
            var tStepEvery = Mustache.render("{{output}}-every", value_dependencies[t]);

            for (var i = 0; i < stepInputs.length; i++) {
              switch(stepInputs[i].getAttribute('id')) {
                // console.log(Mustache.render("{{input}}-start", value_dependencies[t]));
                case tStepStart:
                  sObj['start'] = stepInputs[i];
                  break;
                case tStepEnd:
                  sObj['end'] = stepInputs[i];
                  break;
                case tStepEvery:
                  sObj['every'] = stepInputs[i];
                  break;
              }
            }
            // Write result
            sObj['start'].value = gObj['start'];
            sObj['end'].value = gObj['end'];
            sObj['every'].value = gObj['every'];
          }
          else if (value_dependencies[t].formatting == 'C'){
            //Then we are working with a selectpicker checkbox
            var globalId = Mustache.render("select_{{input}}", value_dependencies[t]);
            var globalCheckbox = $('select[id=' + globalId +']');
            var stepId = Mustache.render("select_{{output}}", value_dependencies[t]);
            var stepCheckbox = $('select[id=' + stepId +']');
            //Set the value and update it
            stepCheckbox.val(globalCheckbox.val());
            stepCheckbox.change();
          }
          else {
            stepInputs[0].value = globalInputs[0].value;
          }
        }
      }
    }
  }
}

dependency.addParameter = function(element){
  var selectedElements = element.parentElement.getElementsByTagName('button')[0].getElementsByClassName('filter-option-inner-inner')[0].innerHTML;
  var elemId = element.id.replace('select_','');
  var outputField = $('#'+elemId)[0];
  var result = "[" + selectedElements + "]";
  if (selectedElements == "Nothing selected") {
    outputField = []
  }
  else {
    outputField.value = JSON.parse(result);
  }
}

getCheckboxVal = function(checkbox_id){
  var stepCheckbox = $('select[id=select_' + checkbox_id.replace("globalParameters-","") +']');
  return stepCheckbox.val();
}
