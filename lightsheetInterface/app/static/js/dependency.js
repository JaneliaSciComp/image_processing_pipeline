/*
 * Custom behavior for the lightsheet landing page
*/
var dependency = dependency || {};

// use template entries from model to apply global parameters
dependency.applyGlobalParameter = function(){
  if (templateObj) {
    for (var t = 0; t < templateObj.length; t++) {
      if (templateObj.pattern) {
        // Do something with the given pattern
      }
      else {
        // We're dealing with array or range parameters
        var globalId = Mustache.render("globalParameters-{{input}}", templateObj[t]);
        var stepId = Mustache.render("{{step}}-{{output}}", templateObj[t]);
        var globalElem = document.getElementById(globalId);
        var stepElem = document.getElementById(stepId);
        if (globalElem && stepElem) {
          var globalInputs = globalElem.getElementsByTagName('input');
          var stepInputs = stepElem.getElementsByTagName('input');
          var gObj = {};
          var sObj = {};
          if (templateObj[t].formatting == 'R') {
            var tGlobalStart = Mustache.render("{{input}}-start", templateObj[t]);
            var tGlobalEnd = Mustache.render("{{input}}-end", templateObj[t]);
            var tGlobalEvery = Mustache.render("{{input}}-every", templateObj[t]);
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
            var tStepStart = Mustache.render("{{output}}-start", templateObj[t]);
            var tStepEnd = Mustache.render("{{output}}-end", templateObj[t]);
            var tStepEvery = Mustache.render("{{output}}-every", templateObj[t]);

            for (var i = 0; i < stepInputs.length; i++) {
              switch(stepInputs[i].getAttribute('id')) {
                // console.log(Mustache.render("{{input}}-start", templateObj[t]));
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
          else {
            stepInputs[0].value = globalInputs[0].value;
          }
        }
      }
    }
  }
}


dependency.addLoadButton = function(element=null){
  if (element) {
    var button = window.document.createElement('input');
    console.log(button);
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