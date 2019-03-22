//Dependencies within a step
$(document).ready(function () {
    lightsheet.testAllCheckboxes()
    document.querySelectorAll("[data-defaultValue*='{']").forEach(//Loop over all fields that have dependencies
        function (element) { //Text fields can have dependencies specified in their defaults, where {dependencyID} denotes replacing the bracketed string with the value of the dependencyID text box
            let currentValue = $(element).attr('data-defaultValue');
            let currentID = "";
            var dependenciesFound = null;
            if (currentValue) {
                var isThisAnEquation = false;
                var mathFinderRegularExpression = /(.*{equation\s+)(.*)(\s+equation}.*)/;
                var newText = currentValue.replace(mathFinderRegularExpression, "$2");
                if (newText != currentValue) {
                    isThisAnEquation = true;
                    currentValue = newText;
                }
                currentID = "#" + $(element).attr("id"); //need this b/c of https://dzone.com/articles/in-place-construction-for-stdany-stdvariant-and-st
                dependenciesFound = currentValue.match(/{[^\s]([^}]+)[^\s]}/g); //get all dependencies by finding text in between brackets, assuming the brackets don't have spaces;
                // those will be reserved for equations: eg for(){ ... }, vs {variableName}
                dependenciesFound = dependenciesFound.filter(onlyUnique);
            }
            if (dependenciesFound != null) {
                for (var i = 0; i < dependenciesFound.length; i++) {//Loop over dependencies for given field with dependency as indicated in data-defaultValue
                    let dependencyFound = dependenciesFound[i];
                    let dependencySubstring = null;
                    //All the following is to get the handle to the current source of the dependency
                    var parameterInformation = getParameterInformation(dependencyFound);
                    dependencySubstring = parameterInformation.parameterName;
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
                            let standardID;
                            var parameterInformation = getParameterInformation(dependenciesFound[j]);
                            standardID = parameterInformation.parameterName;
                            parameterType = parameterInformation.parameterType;
                            let dependencyToUpdate = "#" + standardID; //Current one we are updating
                            let type = $(dependencyToUpdate).prop('type');
                            dependencyToUpdateValue = null; //Initialize dependencyToUpdateValue to null
                            if (type == "checkbox") {//If check box is checked, then dependencyToUpdateValue equals empty string
                                if ($(dependencyToUpdate).prop('checked')) {
                                    dependencyToUpdateValue = standardID.substring(0, dependencySubstring.lastIndexOf('_'));
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
                            updatedValue = updateDependencyString(parameterInformation, dependencyToUpdateValue, updatedValue);
                        }
                        updatedValue = updatedValue.replace(/\s\s+/g, ' '); //remove extra spaces
                        updatedValue = updatedValue.trim(); //remove leading/trailing spaces
                        if (isThisAnEquation) {
                            updatedValue = eval(updatedValue);//TODO: Replace eval with Function
                            if (updatedValue.toString().indexOf("undefined") > -1) {
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
                }
                ;
            }
            ;
//                if (isThisAnEquation){
//                    $(element).val(eval($(element).val()));
//                }
        });
});

$('.selectpicker').selectpicker();