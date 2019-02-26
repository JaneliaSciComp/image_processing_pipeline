//Dependencies within a step
$(document).ready(function () {
    lightsheet.testAllCheckboxes()
    document.querySelectorAll("[data-defaultValue*='{']").forEach(//Loop over all fields that have dependencies
        function (element) { //Text fields can have dependencies specified in their defaults, where {dependencyID} denotes replacing the bracketed string with the value of the dependencyID text box
            let currentValue = $(element).attr('data-defaultValue');
            let currentID = "";
            if (currentValue) {
                var isThisAnEquation = false;
                var mathFinderRegularExpression = /(.*{equation\s+)(.*)(\s+equation}.*)/;
                var newText = currentValue.replace(mathFinderRegularExpression, "$2");
                if (newText != currentValue) {
                    isThisAnEquation = true;
                    currentValue = newText;
                }
                currentID = "#" + $(element).attr("id"); //need this b/c of https://dzone.com/articles/in-place-construction-for-stdany-stdvariant-and-st
                var dependenciesFound = currentValue.match(/{([^}]+)}/g);
            }
            else {
                dependenciesFound = null;
            }
            if (dependenciesFound != null) {
                for (var i = 0; i < dependenciesFound.length; i++) {//Loop over dependencies for given field with dependency as indicated in data-defaultValue
                    let dependencyFound = dependenciesFound[i];
                    let dependencySubstring = null;

                    //All the following is to get the handle to the current source of the dependency
                    if(dependencyFound.slice(-10) ==" filepath}"){//Hacky way to get filepath, filename, basename, extension, loop
                        dependencySubstring = dependencyFound.slice(11,-10);
                    }
                    else if(dependencyFound.slice(-10) ==" filename}"){
                        dependencySubstring = dependencyFound.slice(11,-10);
                    }
                    else if(dependencyFound.slice(-10) ==" basename}"){
                        dependencySubstring = dependencyFound.slice(11,-10);
                    }
                    else if(dependencyFound.slice(-11) ==" extension}"){
                        dependencySubstring = dependencyFound.slice(12,-11);
                    }
                    else {
                        var isThisALoop = dependencyFound.substr(1, dependencyFound.length - 1).match(/{([^}]+)}/g); //Check if loop dependency based on whether it has {{ var }}, after parsing above, will be missing a closing bracket
                        if (isThisALoop != null) {
                            dependencyFound = isThisALoop[0];
                        }
                        dependencySubstring = dependencyFound.substr(1, dependencyFound.length - 2);
                    }
                    stepName = dependencySubstring.split("_");
                    stepName = stepName[stepName.length - 1];
                    let currentDependency = "#" + dependencySubstring;
                    if ($(currentDependency).prop('type') == "hidden") {
                        temp = "select_" + dependencyFound.substr(1, dependencyFound.length - 2);
                        currentDependency = '[data-id="' + temp + '"]'; //multiselect checkbox still acts weird... cant get it to react when clicked or anything
                    }
                    else if ($('input[name=' + dependencySubstring + ']').prop("type")) {
                        //Radiobutton
                        currentDependency = 'input[name=' + dependencySubstring + ']'
                    }
                    $(currentDependency).bind("focus click keyup change checked", function () {
                        let updatedValue = currentValue;
                        for (var j = 0; j < dependenciesFound.length; j++) {//Need to loop through dependencies to ensure that all values are updated, not just the one that was just changed, in case they have some interdependencies
                            loopingOverAllDependenciesCurrentOneBeingProcessed = dependenciesFound[j];
                            var isThisALoop;
                            let standardID;

                            filepathVariable = false;
                            filenameVariable = false;
                            basenameVariable = false;
                            extensionVariable = false; //Hacky way to get filepath, filename, basename, extension, loop
                            if (loopingOverAllDependenciesCurrentOneBeingProcessed.slice(-10) == " filepath}") {
                                standardID = loopingOverAllDependenciesCurrentOneBeingProcessed.slice(11, -10);
                                filepathVariable = true;
                            }
                            else if (loopingOverAllDependenciesCurrentOneBeingProcessed.slice(-10) == " filename}") {
                                standardID = loopingOverAllDependenciesCurrentOneBeingProcessed.slice(11, -10);
                                filenameVariable = true;
                            }
                            else if (loopingOverAllDependenciesCurrentOneBeingProcessed.slice(-10) == " basename}") {
                                standardID = loopingOverAllDependenciesCurrentOneBeingProcessed.slice(11, -10);
                                basenameVariable = true
                            }
                            else if (loopingOverAllDependenciesCurrentOneBeingProcessed.slice(-11) == " extension}") {
                                standardID = loopingOverAllDependenciesCurrentOneBeingProcessed.slice(12, -11);
                                extensionVariable = true;
                            }
                            else {
                                isThisALoop = loopingOverAllDependenciesCurrentOneBeingProcessed.substr(1, loopingOverAllDependenciesCurrentOneBeingProcessed.length - 1).match(/{([^}]+)}/g); //Check if loop dependency based on whether it has {{ var }}, after parsing above, will be missing a closing bracket
                                if (isThisALoop != null) {
                                    loopingOverAllDependenciesCurrentOneBeingProcessed = isThisALoop[0];
                                }
                                standardID = loopingOverAllDependenciesCurrentOneBeingProcessed.substr(1, loopingOverAllDependenciesCurrentOneBeingProcessed.length - 2);
                            }
                            let dependencyToUpdate = "#" + standardID; //Current one we are updating
                            let type = $(dependencyToUpdate).prop('type');
                            dependencyToUpdateValue = null; //Initialize dependencyToUpdateValue to null

                            if (type == "checkbox") {//If check box is checked, then dependencyToUpdateValue equals empty string
                                if ($(dependencyToUpdate).prop('checked')) {
                                    dependencyToUpdateValue = "";
                                }
                            }
                            else if (type == "hidden") {//Multiselect checkbox
                                dependencyToUpdate = "select_" + standardID;
                                dependencyToUpdateValue = $('[data-id="' + dependencyToUpdate + '"]').prop('title');
                                if (dependencyToUpdateValue == "Nothing selected" || dependencyToUpdateValue == undefined) {
                                    dependencyToUpdateValue = null;
                                }
                            }
                            else if ($('input[name=' + standardID + ']').val()) {
                                //radiobutton
                                dependencyToUpdateValue = $('input[name=' + standardID + ']:checked').val()
                            }
                            else if (!($('input[id=emptycheckbox_' + stepName + '-' + standardID + ']').prop('checked'))) {//If it has an empty checkbox that is checked, then keep it empty. Otherwise, take the value
                                //dependencyToUpdateValue takes on the value of the dependency
                                dependencyToUpdateValue = $(dependencyToUpdate).val();
                                if (currentID.includes("parentOutputDirectory")) {
                                    dependencyToUpdateValue = dependencyToUpdateValue.substring(0, dependencyToUpdateValue.lastIndexOf("/"));
                                }
                            }

                            if (standardID.match("^--") || standardID.match("^-")) { //If it starts or ends with a - or --
                                var lastIndex = standardID.lastIndexOf("_");
                                let flagName = standardID.substr(0, lastIndex);
                                if (dependencyToUpdateValue != null) {
                                    if (isThisALoop != null) {//Then this needs to loop
                                        let splitString = dependencyToUpdateValue.split(" ");
                                        dependencyToUpdateValue = "";
                                        for (var k = 0; k < splitString.length; k++) {
                                            if (splitString[k] != "") {
                                                dependencyToUpdateValue = dependencyToUpdateValue + flagName + " " + splitString[k] + " ";
                                            }
                                        }
                                        loopingOverAllDependenciesCurrentOneBeingProcessed = "{" + loopingOverAllDependenciesCurrentOneBeingProcessed + "}";
                                    }
                                    else {
                                        dependencyToUpdateValue = flagName + " " + dependencyToUpdateValue;
                                    }
                                }
                                else {
                                    dependencyToUpdateValue = "";
                                }
                            }
                            if (filepathVariable || filenameVariable || basenameVariable || extensionVariable) {
                                if (filepathVariable) {
                                    var filepath = dependencyToUpdateValue.substring(0, dependencyToUpdateValue.lastIndexOf('/') + 1);
                                    dependencyToUpdateValue = filepath;
                                }
                                else if (filenameVariable) {
                                    var filename = dependencyToUpdateValue.substring(dependencyToUpdateValue.lastIndexOf('/') + 1);
                                    dependencyToUpdateValue = filename;
                                }
                                else if (basenameVariable) {
                                    var filename = dependencyToUpdateValue.substring(dependencyToUpdateValue.lastIndexOf('/') + 1);
                                    var basename = filename.split('.')[0];
                                    dependencyToUpdateValue = basename;
                                }
                                else if (extensionVariable) {
                                    var filename = dependencyToUpdateValue.substring(dependencyToUpdateValue.lastIndexOf('/') + 1);
                                    var extension = '.' + filename.split('.').slice(1).join('.');
                                    dependencyToUpdateValue = extension;
                                }
                                updatedValue = updatedValue.replace(loopingOverAllDependenciesCurrentOneBeingProcessed + "}", dependencyToUpdateValue);
                            }
                            else {
                                stringToReplace = loopingOverAllDependenciesCurrentOneBeingProcessed;
                                var regex = new RegExp(stringToReplace, "g"); //Global replacement
                                updatedValue = updatedValue.replace(regex, dependencyToUpdateValue);
                            }
                        }
                        updatedValue = updatedValue.replace(/\s\s+/g, ' '); //remove extra spaces
                        updatedValue = updatedValue.trim(); //remove leading/trailing spaces
                        if(isThisAnEquation){
                            updatedValue = eval(updatedValue);//TODO: Replace eval with Function
                            if(updatedValue.toString().indexOf("undefined")>-1){
                                updatedValue = "";
                            }
                        }
                        $(currentID).val(updatedValue);
                        $(currentID).text(updatedValue);
                        $(currentID).change(); //So change is propagated
                    });
                    //initialize
                    if (pipelineStepsHaveNotBeenLoaded) { //Then initialize
                        $(currentDependency).trigger("focus");
                        $(currentDependency).trigger("keyup");
                        $(currentDependency).trigger("change");
                    }
                };
            };
//                if (isThisAnEquation){
//                    $(element).val(eval($(element).val()));
//                }
        });
});

$('.selectpicker').selectpicker();