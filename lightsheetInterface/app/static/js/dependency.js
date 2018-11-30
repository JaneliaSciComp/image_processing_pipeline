/*
 * Custom behavior for the lightsheet landing page
*/
var dependency = dependency || {};

// use template entries from model to apply global parameters
dependency.applyGlobalParameter = function () {
    if (value_dependencies) {
        lightsheetStepNames = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR'];
        for (var t = 0; t < value_dependencies.length; t++) {
            var globalStepName = Mustache.render("{{input}}", value_dependencies[t]).split("_");
            globalStepName = globalStepName[globalStepName.length - 1] + "-"; //Needed because different global parameters can be used in a single global parameter step
            var outputStepName = Mustache.render("{{output}}", value_dependencies[t]).split("_");
            outputStepName = outputStepName[outputStepName.length - 1];
            var isLightsheet = lightsheetStepNames.indexOf(outputStepName) >= 0;
            var globalId = Mustache.render("divisionFor-{{input}}", value_dependencies[t]);
            var stepId = Mustache.render("divisionFor-{{output}}", value_dependencies[t]);
            var globalElem = document.getElementById(globalId);
            var stepElem = document.getElementById(stepId);
            if (value_dependencies[t].pattern) {
                // Do something with the given pattern
                var pattern = value_dependencies[t].pattern;
                var variables = pattern.match(/[^\{\]]+(?=\})/g);
                for (var i = 0; i < variables.length; i++) {
                    var currentVariableId;
                    loopVariable = false;
                    if (variables[i].slice(-1) == "}") { //Hacky way to get loop variable
                        variables[i] = variables[i].slice(0, -1);
                        loopVariable = true;
                    }
                    currentVariableId = "divisionFor-" + variables[i];
                    needToFormat = false;
                    if (currentVariableId.includes("_string") && isLightsheet) { //Specific to lightsheet
                        needToFormat = true;
                        currentVariableId = currentVariableId.replace("_string", "");
                    }
                    if (currentVariableId.includes("cameras") || currentVariableId.includes("channels") && isLightsheet) {//Specific to lightsheet
                        currentVariableValue = getCheckboxVal(globalStepName, currentVariableId);
                    }
                    else {//More generic handling of global params, ie, not specific to Lightsheet
                        var globalElem = document.getElementById(currentVariableId);
                        var globalInputs = globalElem.getElementsByTagName('input');
                        var currentVariableValue = globalInputs[0].value;

                        checkboxId = globalId.split("-")[1];
                        if (globalId.includes("useOutputFolderForClusterPT") && isLightsheet) { //Specific to lightsheet
                            if (document.getElementById(checkboxId).checked) {
                                if (currentVariableId.includes("inputFolder")) {
                                    currentVariableValue = "/" + globalInputs[0].value.match(/([^\/]*)\/*$/)[1]; //get last folder
                                }
                            }
                            else {
                                currentVariableValue = ""
                            }
                        }
                        else if (isLightsheet) {
                            if (currentVariableId.includes("inputFolder")) {//If useOutputFolderForClusterPT checkbox is checked need to do this so that the correct directory is used
                                checkboxId = document.querySelector('[id*="useOutputFolderForClusterPT"]').id.split("-")[1];
                                if (document.getElementById(checkboxId).checked) {
                                    outputFolderId = "outputFolder_" + globalStepName.slice(0, -1);
                                    inputFolderId = "inputFolder_" + globalStepName.slice(0, -1);
                                    outputFolder = document.getElementById(outputFolderId).value;
                                    inputFolderLastDir = document.getElementById(inputFolderId).value.match(/([^\/]*)\/*$/)[1]
                                    currentVariableValue = outputFolder + "/" + inputFolderLastDir;
                                }
                            }
                        }
                    }
                    if (needToFormat) {
                        var prefix;
                        if (currentVariableId.includes("specimen")) {
                            prefix = "SPM";
                            iterations = 1; //need this because this is a string and don't want to iterate through each character
                        }
                        else if (currentVariableId.includes("cameras")) {
                            prefix = "CM";
                            iterations = currentVariableValue.length;
                        }
                        else if (currentVariableId.includes("channels")) {
                            prefix = "CHN";
                            iterations = currentVariableValue.length;
                        }
                        var currentVariableValueFormatted = "";
                        for (var j = 0; j < iterations; j++) {
                            currentVariableValueFormatted = currentVariableValueFormatted + (prefix + "0" + currentVariableValue[j].replace(".0", "") + "_");
                        }
                        currentVariableValue = currentVariableValueFormatted.slice(0, -1); //Remove trailing "_"
                    }
                    if (loopVariable) {
                        currentVariableValueSplit = currentVariableValue.split(" ");//Split on space
                        loopedPattern = "";
                        for (var loopVariableIndex = 0; loopVariableIndex < currentVariableValueSplit.length; loopVariableIndex++) {
                            loopedPattern = loopedPattern + pattern.replace("{{" + variables[i] + "}}", currentVariableValueSplit[loopVariableIndex]) + " ";
                        }
                        pattern = loopedPattern.slice(0, -1);
                    }
                    else {
                        pattern = pattern.replace("{" + variables[i] + "}", currentVariableValue);
                    }
                }
                pattern = pattern.replace("//", "/");
                var stepInputs = stepElem.getElementsByTagName('input');
                stepInputs[0].value = pattern;
                var stepInputForChanging = Mustache.render("#{{output}}", value_dependencies[t]);
                $(stepInputForChanging).change();
            }
            else {
                // We're dealing with array or range parameters, or it is just taking the same exact value
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
                            switch (globalInputs[i].getAttribute('id')) {
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
                            switch (stepInputs[i].getAttribute('id')) {
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
                    else if (value_dependencies[t].formatting == 'C') {
                        //Then we are working with a selectpicker checkbox
                        var globalId = Mustache.render("select_{{input}}", value_dependencies[t]);
                        var globalCheckbox = $('select[id=' + globalId + ']');
                        var stepId = Mustache.render("select_{{output}}", value_dependencies[t]);
                        var stepCheckbox = $('select[id=' + stepId + ']');
                        //Set the value and update it
                        stepCheckbox.val(globalCheckbox.val());
                        stepCheckbox.change();
                    }
                    else {
                        stepInputs[0].value = globalInputs[0].value;
                        var stepInputForChanging = Mustache.render("#{{output}}", value_dependencies[t]);
                        $(stepInputForChanging).change(); //Mark it is changed
                    }
                }
            }
        }
    }
};

dependency.addParameter = function (element) {
    var selectedElements = element.parentElement.getElementsByTagName('button')[0].getElementsByClassName('filter-option-inner-inner')[0].innerHTML;
    var elemId = element.id.replace('select_', '');
    var outputField = $('#' + elemId)[0];
    var result = "[" + selectedElements + "]";
    if (selectedElements == "Nothing selected") {
        outputField = []
    }
    else {
        outputField.value = JSON.parse(result);
    }
};

getCheckboxVal = function (globalStepName, checkbox_id) {
    var stepCheckbox = $('select[id=select_' + checkbox_id.replace("divisionFor-", "") + ']');
    return stepCheckbox.val();
};
