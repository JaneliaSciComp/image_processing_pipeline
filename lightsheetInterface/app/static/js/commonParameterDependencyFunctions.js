function getParameterInformation(parameterString) {
    parameterType = "standard";
    if (parameterString.indexOf(' ') < 0) {//Check if it has whitespace, if it does then it is one of the filepath things
        parameterName = parameterString.substr(1, parameterString.length - 2);
    }
    else if (parameterString != parameterString.replace(/(.*{filepath\s+)(.*)(\s+filepath}.*)/, "$2")) {//Hacky way to get filepath, filename, basename, extension, loop
        parameterName = parameterString.replace(/(.*{filepath\s+)(.*)(\s+filepath}.*)/, "$2");
        parameterType = "filepath";
    }
    else if (parameterString != parameterString.replace(/(.*{filename\s+)(.*)(\s+filename}.*)/, "$2")) {
        parameterName = parameterString.replace(/(.*{filename\s+)(.*)(\s+filename}.*)/, "$2");
        parameterType = "filename";
    }
    else if (parameterString != parameterString.replace(/(.*{basename\s+)(.*)(\s+basename}.*)/, "$2")) {
        parameterName = parameterString.replace(/(.*{basename\s+)(.*)(\s+basename}.*)/, "$2");
        parameterType = "basename";
    }
    else if (parameterString != parameterString.replace(/(.*{extension\s+)(.*)(\s+extension}.*)/, "$2")) {
        parameterName = parameterString.replace(/(.*{extension\s+)(.*)(\s+extension}.*)/, "$2");
        parameterType = "extension";
    }
    else if (parameterString != parameterString.replace(/(.*{loop\s+)(.*)(\s+loop}.*)/, "$2")) {
        parameterName = parameterString.replace(/(.*{loop\s+)(.*)(\s+loop}.*)/, "$2");
        parameterType = "loop";
    }
    return {
        parameterPatternString: parameterString,
        parameterName: parameterName,
        parameterType: parameterType
    }
}

function updateDependencyString(parameterInformation, parameterValue, stringToUpdate) {
    parameterPatternString = parameterInformation.parameterPatternString;
    parameterName = parameterInformation.parameterName;
    parameterType = parameterInformation.parameterType;
    if (parameterValue == null) {
        parameterValue = "";
    }
    else {
        if (parameterType == "standard" || parameterType == "loop") {
            var lastIndex = parameterName.lastIndexOf("_");
            let flagNameString = "";
            if (parameterName[0] == '-') { //If it starts or ends with a -
                flagNameString = parameterName.substr(0, lastIndex) + " ";
            }
            if (parameterType == "loop") {//Then this needs to loop
                let splitString = parameterValue.split(" ");
                parameterValue = "";
                for (var k = 0; k < splitString.length; k++) {
                    if (splitString[k] != "") {
                        parameterValue = parameterValue + flagNameString + splitString[k] + " ";
                    }
                }
            }
            else {
                parameterValue = flagNameString + parameterValue;
            }
        }
        else {
            if (parameterType == "filepath") {
                var filepath = parameterValue.substring(0, parameterValue.lastIndexOf('/') + 1);
                parameterValue = filepath;
            }
            else if (parameterType == "filename") {
                var filename = parameterValue.substring(parameterValue.lastIndexOf('/') + 1);
                parameterValue = filename;
            }
            else if (parameterType == "basename") {
                var filename = parameterValue.substring(parameterValue.lastIndexOf('/') + 1);
                var basename = filename.split('.')[0];
                parameterValue = basename;
            }
            else if (parameterType == "extension") {
                var filename = parameterValue.substring(parameterValue.lastIndexOf('/') + 1);
                var extension = '.' + filename.split('.').slice(1).join('.');
                parameterValue = extension;
            }
        }
    }
    var regex = new RegExp(parameterPatternString, "g"); //Global replacement
    var updatedString = stringToUpdate.replace(regex, parameterValue);
    return updatedString;
}

function onlyUnique(value, index, self) {
    return self.indexOf(value) === index;
}
