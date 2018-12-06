/*
 * Custom behavior for the lightsheet landing page
*/
var dataIo = dataIo || {};

dataIo.fetch = function (url, method, data, params) {
    return fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    }).then(function (response) {
        if (response.status == 200) {
            return response.json();
        }
        throw new Error('Unexpected status code: ' + response.status);
    });
};

dataIo.handleError = function (err) {
    console.log(err);
};

/*
 * Grab data and submit it when pressing the button
 */
dataIo.grabData = function () {
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
    checked_boxes.each(function (index, element) {
        const step = this.id.replace('check-', '');
        const checked_boxes = $('form :input[id^=check-]:checked');
        var stepType = document.getElementById("check-" + step).getAttribute("data-steptype");

        data[step] = {};
        pausecheck = document.getElementById('pausecheck-' + step);
        if (pausecheck) {
            data[step]['pause'] = 0;
            if (pausecheck.checked) {
                data[step]['pause'] = 1;
            }
        }
        if (stepType) {
            if (stepType == 'L') {
                data[step]['type'] = 'LightSheet';
            }
            else if (stepType == 'Sp') {
                data[step]['type'] = 'Sparks';
            }
            else if (stepType == 'Si') {
                data[step]['type'] = 'Singularity';
            }
        }

        // input fields
        var inputFields = $('#collapse' + step).find('input:not([ignore])');
        const p = 'parameters';
        data[step][p] = {};

        var bindPath = [];
        inputFields.each(function (k, val) {
            if (this.hasAttribute('mount')) {
                bindPath.push(val.value);
            }
            if (!this.hasAttribute('ignore')) {
                if (this.disabled) {
                    data[step][p][val.id] = '';
                }
                else {
                    if (val.type == 'radio') {
                        radioButtonValue = $('#collapse' + step).find('input[name=\"' + val.name + '\"]:checked').val();
                        data[step][p][val.name] = radioButtonValue;
                    }
                    else if (val.type == 'checkbox') { // For checkbox parameters, only add value if it's true
                        if (val.checked !== undefined && val.checked !== false && val.checked !== 'false') {
                            data[step][p][val.id] = 'True';
                        }
                        else {
                            data[step][p][val.id] = 'False';
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

dataIo.customSubmit = function () {
    //During submit, loop through jobLoop_params
   var jobLoopParameters = $('*[id^="jobLoop_"]');
    if(jobLoopParameters.length !=0 && !jobLoopParameters.disabled && jobLoopParameters[0].value!="") {
        loopParametersJobSubmission();
    }
    else{
        data = dataIo.grabData();
       dataIo.fetch(window.location, 'POST', data)
           .catch(dataIo.handleError);
    }
};

dataIo.reset = function (stepOrTemplateName, id) {
    var baseUrl = window.location.origin;
    window.location.replace(baseUrl + stepOrTemplateName + "?lightsheetDB_id=" + id + "&reparameterize=true");
};

dataIo.downloadSettings = function (stepOrTemplateName) {
    var jobLoopParameters = $('*[id^="jobLoop_"]');
    link = document.getElementById("downloadURL");
    data = dataIo.grabData();
    var baseUrl = window.location.origin;
    response = dataIo.fetch(baseUrl + '/download_settings/?stepOrTemplateName=' + stepOrTemplateName, 'POST', data);
    response.then(function (result) {
        filename = result["name"] + ".json";
        result["stepOrTemplateName"] = stepOrTemplateName;
        dataString = JSON.stringify(result, null, 2);
        var blob = new Blob([dataString], {type: "application/json"});
        var url = URL.createObjectURL(blob);
        var a = link;
        a.download = filename;
        a.href = url;
        a.click();
        a.href = "javascript:;";
    })
};

loopParametersJobSubmission = function () {
    //Beginning to apply simple loop parameters
    var jobLoopParameters = $('*[id^="jobLoop_"]');
    var arrayOfJobLoopParameters = [];
    for (var i in jobLoopParameters) {
        if (jobLoopParameters[i].value) {//Then not empty
            arrayOfJobLoopParameters = JSON.parse("[" + jobLoopParameters[i].value + "]");
        }
    }
    for (var loopNumber = 0; loopNumber < arrayOfJobLoopParameters.length; loopNumber++) {
        replaceParameterId = jobLoopParameters[0].id.replace("jobLoop_", "");
        var isSelectPicker = $('[id="select_' + replaceParameterId + '"]');
        if (isSelectPicker.length) {
            $('[id="select_' + replaceParameterId + '"]').selectpicker('val', arrayOfJobLoopParameters[loopNumber]);
        }
        else {
            $('[id="' + replaceParameterId + '"]').val(arrayOfJobLoopParameters[loopNumber])
        }
        dependency.applyGlobalParameter();
        data = dataIo.grabData();
        paramName = replaceParameterId.substring(0,replaceParameterId.lastIndexOf("_"));
        data.jobName = data.jobName + "_"+paramName+("000" + arrayOfJobLoopParameters[loopNumber]).slice(-3);
        dataIo.fetch(window.location, 'POST', data)
            .catch(dataIo.handleError);
    }
}

