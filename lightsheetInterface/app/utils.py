import datetime, json, requests, operator, time
from flask import url_for
from flask_login import current_user
from mongoengine import ValidationError, NotUniqueError
from datetime import datetime
from pytz import timezone
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from app import app
from app.models import AppConfig, Step, Parameter, Template, PipelineInstance
from collections import OrderedDict
from itertools import repeat

# JACS server
jacs_host = app.config.get('JACS_HOST')


# collect the information about existing job used by the job_status page
def getJobInfoFromDB(imageProcessingDB, _id=None, parentOrChild="parent"):
    allSteps = Step.objects.all()
    if _id:
        _id = ObjectId(_id)

    if parentOrChild == "parent":
        parentJobInfo = list(imageProcessingDB.jobs.find({"username": current_user.username,"hideFromView":{"$ne":1}}, {"configAddress": 1, "state": 1, "jobName": 1, "remainingStepNames":1,
                                                              "creationDate": 1, "jacs_id": 1, "steps.name": 1,
                                                              "steps.state": 1}))
        for currentJobInfo in parentJobInfo:
            selectedStepNames = ''
            for step in currentJobInfo["steps"]:
                stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]),
                                    None)
                if stepTemplate == None or stepTemplate.submit:  # None implies a deprecated name
                    selectedStepNames = selectedStepNames + step["name"] + ','
            selectedStepNames = selectedStepNames[:-1]
            currentJobInfo.update({'selectedStepNames': selectedStepNames})
            currentJobInfo.update({"selected": ""})
            if _id:
                if currentJobInfo["_id"] == _id:
                    currentJobInfo.update({"selected": "selected"})
        return parentJobInfo
    elif parentOrChild == "child" and _id:
        childJobInfo = []
        tempList = list(imageProcessingDB.jobs.find({"username": current_user.username, "_id": _id},
                                                    {"remainingStepNames":1,"stepOrTemplateName": 1, "steps.name": 1, "steps.state": 1,
                                                     "steps.creationTime": 1, "steps.endTime": 1,
                                                     "steps.elapsedTime": 1, "steps.logAndErrorPath": 1,
                                                     "steps.pause": 1, "steps._id":1}))
        tempList = tempList[0]
        remainingStepNames = tempList["remainingStepNames"]
        for step in tempList["steps"]:
            stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]), None)
            if stepTemplate == None or stepTemplate.submit:  # None implies a deprecated name
                childJobInfo.append(step)
        if 'stepOrTemplateName' in tempList and tempList['stepOrTemplateName'] is not None:
            stepOrTemplateName = tempList["stepOrTemplateName"]
            stepOrTemplateNamePath = stepOrTemplateNamePathMaker(stepOrTemplateName)
        else:
            stepOrTemplateName = ''
            stepOrTemplateNamePath = ''
        return stepOrTemplateName, stepOrTemplateNamePath, childJobInfo, remainingStepNames
    else:
        return 404


# build result object of existing job information
def mapJobsToDict(x, allSteps):
    result = {}
    allParameters = ['username', 'jobName', 'username', 'creationDate', 'state', 'jacs_id', '_id', 'submissionAddress', 'stepOrTemplateName' ]
    for currentParameter in allParameters:
        if currentParameter in x:
            if currentParameter == '_id':
                result['id'] = str(x[currentParameter]) if str(x[currentParameter]) is not None else ''
            elif currentParameter == 'stepOrTemplateName':
                if x['stepOrTemplateName'] is not None:
                    result['stepOrTemplateName'] = stepOrTemplateNamePathMaker(x['stepOrTemplateName'])
                    result["jobType"] = x['stepOrTemplateName']
                else:
                    result['stepOrTemplateName'] = ''
                    result["jobType"] = ''
            else:
                result[currentParameter] = x[currentParameter] if x[currentParameter] is not None else ''
        elif currentParameter == 'submissionAddress':
            result['submissionAddress'] = ''
        elif currentParameter == 'stepOrTemplateName':
            result['stepOrTemplateName'] = ''
            result["jobType"] = ''

    result['selectedSteps'] = {'names': '', 'states': '', 'submissionAddress': ''}
    for i, step in enumerate(x["steps"]):
        stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]), None)
        if stepTemplate == None or stepTemplate.submit:  # None implies a deprecated name
            result['selectedSteps']['submissionAddress'] = result['submissionAddress']
            result['selectedSteps']['names'] = result['selectedSteps']['names'] + step["name"] + ','
            result['selectedSteps']['states'] = result['selectedSteps']['states'] + step["state"] + ','
            if step['state'] not in ["CREATED", "SUCCESSFUL", "RUNNING", "NOT YET QUEUED", "QUEUED", "DISPATCHED"]:
                if step["name"] in x['remainingStepNames']:
                    result['selectedSteps']['states']=result['selectedSteps']['states']+ 'RESET,'
            elif "pause" in step and step['pause'] and step['state'] == "SUCCESSFUL":
                if step["name"] in x['remainingStepNames']:
                    result['selectedSteps']['states'] = result['selectedSteps']['states'] + 'RESUME,RESET,'
    result['selectedSteps']['names'] = result['selectedSteps']['names'][:-1]
    result['selectedSteps']['states'] = result['selectedSteps']['states'][:-1]
    return result


# get job information used by jquery datatable
def allJobsInJSON(imageProcessingDB,showAllJobs=False):
    if showAllJobs:
        parentJobInfo = imageProcessingDB.jobs.find({"username": {"$exists": "true"}, "hideFromView":{"$ne":1}}, {"_id": 1, "username": 1, "jobName": 1, "remainingStepNames":1, "submissionAddress": 1, "creationDate": 1,
                                                                                                                  "state": 1, "jacs_id": 1, "stepOrTemplateName": 1,
                                                                                                                 "steps.state": 1, "steps.name": 1, "steps.pause": 1})
    else:
        parentJobInfo = imageProcessingDB.jobs.find({"username":current_user.username, "hideFromView":{"$ne":1}}, {"_id": 1, "jobName": 1, "remainingStepNames":1, "submissionAddress": 1, "creationDate": 1,
                                                    "state": 1, "jacs_id": 1, "stepOrTemplateName": 1,
                                                    "steps.state": 1, "steps.name": 1, "steps.pause": 1})
    allSteps = Step.objects.all()
    listToReturn = list(map(mapJobsToDict, parentJobInfo, repeat(allSteps)))
    return listToReturn


# build object with meta information about parameters from the admin interface
def getParameters(parameters):
    for parameter in parameters:
        if parameter.number1 != None:
            parameter.type = 'Integer'
            if parameter.number2 == None:
                parameter.count = '1'
            elif parameter.number3 == None:
                parameter.count = '2'
            elif parameter.number4 == None:
                parameter.count = '3'
            elif parameter.number5 == None:
                parameter.count = '4'
            elif parameter.number6 == None:
                parameter.count = '5'
            else:
                parameter.count = '6'
        elif parameter.float1:
            parameter.type = 'Float'
            parameter.count = '1'
        elif parameter.text1:
            parameter.type = 'Text'
            if not parameter.text2:
                parameter.count = '1'
            elif not parameter.text3:
                parameter.count = '2'
            elif not parameter.text4:
                parameter.count = '3'
            elif not parameter.text5:
                parameter.count = '4'
            else:
                parameter.count = '5'

    return parameters


# build object with information about steps and parameters about admin interface
def buildConfigObject(stepOrTemplateDictionary=None):
    try:
        currentSteps = []
        #Check if we are loading a default step/template in which case we just need to load the corresponding information
        #Else, we need to load all possible settings since we are loading a deprecated step/template name which may contain steps in order we don't expect
        if stepOrTemplateDictionary:
            if 'step' in stepOrTemplateDictionary:
                stepName = stepOrTemplateDictionary['step']
                currentSteps = Step.objects.all().filter(name=stepName)[0]
                currentSteps['parameter'] = getParameters(currentSteps.parameter)
                currentSteps = [currentSteps]
            elif 'template' in stepOrTemplateDictionary:
                templateName = stepOrTemplateDictionary['template']
                template = Template.objects.all().filter(name=templateName)
                currentSteps = sorted(template[0].steps, key=operator.attrgetter('order'))
                for step in currentSteps:
                    step['parameter'] = getParameters(step['parameter'])
            elif 'steps' in stepOrTemplateDictionary:
                for tempStep in stepOrTemplateDictionary['steps']:
                    if 'name' in tempStep:
                        stepName = tempStep['name']
                    else:
                        stepName = tempStep
                    step = Step.objects.all().filter(name=stepName)[0]
                    step['parameter'] = getParameters(step['parameter'])
                    currentSteps.append(step)
        else:
            allSteps = Step.objects.all()
            for step in allSteps:
                step['parameter'] = getParameters(step['parameter'])
                currentSteps.append(step)
        
        config = {
            'steps': currentSteps,
            'stepNames': getStepNames(),
            'templateNames': getTemplateNames()
        }

    except ServerSelectionTimeoutError:
        return 404
    return config


def getStepNames():
    return Step.objects.all().values_list('name')


def getTemplateNames():
    return Template.objects.all().order_by('order').values_list('name')


# Header for post request
def getHeaders(forQuery=False):
    if forQuery:
        return {
            'content-type': 'application/json',
            'USERNAME': current_user.username if current_user.is_authenticated else ""
        }
    else:
        # for now runasuser is the same as the authenticated user
        # but maybe in the future the feature will be supported
        return {
            'content-type': 'application/json',
            'USERNAME': current_user.username if current_user.is_authenticated else "",
            #'RUNASUSER': current_user.username if current_user.is_authenticated else ""
        }


# Timezone for timings
eastern = timezone('US/Eastern')
UTC = timezone('UTC')


# get step information about existing jobs from db
def getJobStepData(_id, imageProcessingDB):
    result = getConfigurationsFromDB(_id, imageProcessingDB, stepName=None)
    if result != None and result != 404 and len(result) > 0 and 'steps' in result[0]:
        return result[0]['steps']
    return None


# get the job parameter information from db
def getConfigurationsFromDB(imageProcessingDB_id, imageProcessingDB, globalParameter=None, stepName=None,
                            stepParameter=None):
    output = {}
    if globalParameter:
        globalParameterValue = list(
            imageProcessingDB.jobs.find({'_id': ObjectId(imageProcessingDB_id)}, {'_id': 0, globalParameter: 1}))
        output = globalParameterValue[0]
        if not output:
            output = {globalParameter: ""}
    else:
        if stepName:
            output = list(
                imageProcessingDB.jobs.find({'_id': ObjectId(imageProcessingDB_id), 'steps.name': stepName},
                                            {'_id': 0, "steps.$":1}))
            if output:
                output = output[0]["steps"][0]["parameters"]
        else:
            output = list(imageProcessingDB.jobs.find({'_id': ObjectId(imageProcessingDB_id)}, {'_id': 0, 'steps': 1}))

    if output:
        return output
    return 404

# get latest status information about jobs from db
def updateDBStatesAndTimes(imageProcessingDB,showAllJobs=False):
    if current_user.is_authenticated:
        if showAllJobs:
            allJobInfoFromDB = list(imageProcessingDB.jobs.find({"username": {"$exists": "true"},"state": {"$in": ["NOT YET QUEUED","RUNNING", "CREATED","QUEUED","DISPATCHED"]}}))
        else:
            allJobInfoFromDB = list(imageProcessingDB.jobs.find(
                                {"username": current_user.username,
                                 "state": {"$in": ["NOT YET QUEUED","RUNNING", "CREATED","QUEUED","DISPATCHED"]}}))
        for parentJobInfoFromDB in allJobInfoFromDB:
            if 'jacs_id' in parentJobInfoFromDB:  # TODO handle case, when jacs_id is missing
                # if parentJobInfoFromDB["state"] in ['NOT YET QUEUED', 'RUNNING']: #Don't need this now not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
                if isinstance(parentJobInfoFromDB["jacs_id"], list):
                    jacs_ids = parentJobInfoFromDB["jacs_id"]
                else:
                    jacs_ids = [parentJobInfoFromDB["jacs_id"]]

                for jacs_id in jacs_ids:
                    parentJobInfoFromJACS = requests.get(jacs_host + ':9000/api/rest-v2/services/',
                                                         params={'service-id': jacs_id},
                                                         headers=getHeaders(True)).json()
                    if parentJobInfoFromJACS and len(parentJobInfoFromJACS["resultList"]) > 0:
                        parentJobInfoFromJACS = parentJobInfoFromJACS["resultList"][0]
                        imageProcessingDB.jobs.update_one({"_id": parentJobInfoFromDB["_id"]},
                                                          {"$set": {"state": parentJobInfoFromJACS["state"]}})
                        allChildJobInfoFromJACS = requests.get(jacs_host + ':9000/api/rest-v2/services/',
                                                               params={'parent-id': jacs_id},
                                                               headers=getHeaders(True)).json()
                        allChildJobInfoFromJACS = allChildJobInfoFromJACS["resultList"]
                        if allChildJobInfoFromJACS:
                            for currentChildJobInfoFromDB in parentJobInfoFromDB["steps"]:
                                currentChildJobInfoFromJACS = next((step for step in allChildJobInfoFromJACS if
                                                                    (currentChildJobInfoFromDB["name"] in step["description"]) ), None)
                                if currentChildJobInfoFromDB["state"]=="NOT YET QUEUED" and jacs_id!=jacs_ids[-1]: #NOT YET QUEUED jobs were just submitted so only want to check based on currently running job
                                        currentChildJobInfoFromJACS = False
                                if currentChildJobInfoFromJACS:
                                        creationTime = convertJACStime(currentChildJobInfoFromJACS["processStartTime"])
                                        outputPath = "N/A"
                                        if "outputPath" in currentChildJobInfoFromJACS:
                                            outputPath = currentChildJobInfoFromJACS["outputPath"][:-11]
                                        imageProcessingDB.jobs.update_one({"_id": parentJobInfoFromDB["_id"],
                                                                           "steps.name": currentChildJobInfoFromDB["name"]},
                                                                          {"$set": {
                                                                              "steps.$.state": currentChildJobInfoFromJACS["state"],
                                                                              "steps.$.creationTime": creationTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                                              "steps.$.elapsedTime": str(datetime.now(eastern).replace(microsecond=0) - creationTime),
                                                                              "steps.$.logAndErrorPath": outputPath,
                                                                              "steps.$._id": currentChildJobInfoFromJACS["_id"]
                                                                              }})

                                        if currentChildJobInfoFromJACS["state"] in ['CANCELED', 'TIMEOUT', 'ERROR','SUCCESSFUL']:
                                            endTime = convertJACStime(currentChildJobInfoFromJACS["modificationDate"])
                                            imageProcessingDB.jobs.update_one({"_id": parentJobInfoFromDB["_id"],
                                                                               "steps.name": currentChildJobInfoFromDB["name"]},
                                                                              {"$set": {"steps.$.endTime": endTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                                                        "steps.$.elapsedTime": str(endTime - creationTime)
                                                                                        }})


def convertJACStime(t):
    t = datetime.strptime(t[:-9], '%Y-%m-%dT%H:%M:%S')
    t = UTC.localize(t).astimezone(eastern)
    return t


def createDBentries(content):
    message = []
    success = False
    if type(content) is list:
        content = content[0]
    keys = content.keys()
    for key in keys:
        obj = content[key]
        if key == 'parameters':
            for o in obj:
                p = Parameter()
                p.name = o
                p.displayName = o
                value = obj[o]
                if type(value) is dict:
                    if 'start' in value and 'end' in value and 'every' in value:
                        p.frequency = 'F'
                        p.formatting = 'R'
                        p.number1 = value['start']
                        p.number2 = value['end']
                        p.number3 = value['every']
                else:
                    p.frequency = 'F'
                    if type(value) == str:
                        p.text1 = value
                    elif type(value) == float:
                        p.number1 = value
                    elif type(value) == list:
                        #TODO: distinguish in between the different types
                        continue
                try:
                    p.save()
                except OSError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except ValidationError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except NotUniqueError as e:
                    message.append('Parameter with the name "{0}" has already been added: '.format(p['name']))
                    pass
        elif key == 'steps':
            for o in obj:
                s = Step()
                if 'name' in o:
                    s['name'] = o['name']
                if 'order' in o:
                    s['order'] = o['order']
                if 'description' in o:
                    s['description'] = o['description']
                if 'parameters' in o:
                    # Query for steps and associate them with template
                    for param in o['parameters']:
                        pObj = Parameter.objects.filter(name=param).first()
                        if pObj:
                            s['parameter'].append(pObj.pk)
                try:
                    s.save()
                except ValidationError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except NotUniqueError as e:
                    message.append('Step with the name "{0}" has already been added.'.format(o['name']))
                    pass
        elif key == 'template':
            for o in obj:
                t = Template()
                if 'name' in o:
                    t.name = o['name']
                if 'steps' in o:
                    # Query for steps and associate them with template
                    for step in o['steps']:
                        stepObj = Step.objects.filter(name=step).first()
                        if stepObj:
                            t['steps'].append(stepObj)
                        else:
                            print('No step object found')
                try:
                    t.save()
                except ValidationError as e:
                    message.append('Error creating the template: ' + str(e))
                    pass
                except NotUniqueError as e:
                    message.append('Template with the name "{0}" has already been added.'.format(o['name']))
                    pass
                except:
                    message.append('There was an error creating a template')
                    pass

    if len(message) == 0:
        success = True
        message.append('File has been uploaded successfully.')

    result = {}
    result['message'] = message
    result['success'] = success
    return result


def createConfig(content):
    pInstance = PipelineInstance()
    jsonObj = json.dumps(OrderedDict(content))
    pInstance.content = jsonObj

    if 'name' in content:
        pInstance.description = content['name']
    pInstance.save()

    message = []
    result = {}
    # Create new database objects configuration and configuration instances
    result['message'] = message
    result['success'] = True
    result['name'] = pInstance.name
    return result

def submitToJACS(config_server_url, imageProcessingDB, job_id, continueOrReparameterize):
    job_id = ObjectId(job_id)
    configAddress = config_server_url + "config/{}".format(job_id)

    jobInfoFromDatabase = list(imageProcessingDB.jobs.find({"_id":job_id}))
    jobInfoFromDatabase=jobInfoFromDatabase[0]
    remainingSteps = []
    remainingStepNames  = jobInfoFromDatabase["remainingStepNames"]
    pauseState = False
    currentStepIndex = 0
    while pauseState == False and currentStepIndex < len(jobInfoFromDatabase["steps"]):
        step = jobInfoFromDatabase["steps"][currentStepIndex]
        if step["name"] in remainingStepNames:
            remainingSteps.append(step)
            if ("pause" in step):
                pauseState = step["pause"]
        currentStepIndex = currentStepIndex + 1
    postBody = {"ownerKey": "user:"+current_user.username if current_user.is_authenticated else ""}
    postBody["resources"] = {"gridAccountId": current_user.username}

    pipelineServices = []
    for step in remainingSteps:
        if step["type"] == "LightSheet":
            stepPostBody = step
            stepPostBody["stepResources"]= {"softGridJobDurationInSeconds": "1200"}
        elif step["type"] == "Sparks":
            stepPostBody = {
                "stepName": step["name"],
                "serviceName": "sparkAppProcessor",
                "serviceProcessingLocation": 'LSF_JAVA',
                "serviceArgs": [
                    "-appLocation", step["codeLocation"],
                    "-appEntryPoint", step["entryPointForSpark"],
                    "-appArgs", step["parameters"]["-appArgs"]
                ]}
            if "-numNodes" in step["parameters"]:
                stepPostBody["serviceResources"] = {"sparkNumNodes": str(int(step["parameters"]["-numNodes"]))}
        else:  # Singularity
            stepPostBody = {
                "stepName": step["name"],
                "serviceName": "runSingularityContainer",
                "serviceProcessingLocation": 'LSF_JAVA',
                "serviceArgs": [
                    "-containerLocation", step["codeLocation"],
                    "-singularityRuntime", "/usr/bin/singularity",
                    "-bindPaths", step["bindPaths"],
                    "-appArgs", step["parameters"]["-appArgs"]
                ]
            }
            if "numberOfProcessors" in step["parameters"]:
                stepPostBody["serviceResources"] = {"nSlots": str(int(step["parameters"]["numberOfProcessors"]))}
            for argName in ["-expandDir", "-expandPattern", "-expandedArgFlag", "-expandedArgList", "-expandDepth"]:
                if argName in step["parameters"]:
                    stepPostBody["serviceArgs"].extend((argName, step["parameters"][argName]))

        pipelineServices.append(stepPostBody)
    if remainingSteps[0]['type'] == "LightSheet":
        postUrl = jacs_host + ':9000/api/rest-v2/async-services/lightsheetPipeline'
        postBody['processingLocation']= 'LSF_JAVA'
        postBody["dictionaryArgs"]={"pipelineConfig": {"steps": pipelineServices}}
    else:
        postUrl = jacs_host + ':9000/api/rest-v2/async-services/pipeline'
        postBody["dictionaryArgs"]={"pipelineConfig": {"pipelineServices": pipelineServices}}
    try:
        requestOutput = requests.post(postUrl,
                                      headers=getHeaders(),
                                      data=json.dumps(postBody))
        requestOutputJsonified = requestOutput.json()
        creationDate = job_id.generation_time
        creationDate = str(creationDate.replace(tzinfo=UTC).astimezone(eastern))
        if continueOrReparameterize:
            imageProcessingDB.jobs.update_one({"_id": job_id}, {"$set": {"state": "NOT YET QUEUED"}, "$push": {
                "jacsStatusAddress": jacs_host + '8080/job/' + requestOutputJsonified["_id"],
                "jacs_id": requestOutputJsonified["_id"]}})
        else:
            imageProcessingDB.jobs.update_one({"_id": job_id}, {
                "$set": {"jacs_id": [requestOutputJsonified["_id"]], "configAddress": configAddress,
                         "creationDate": creationDate[:-6]}})

        # JACS service states
        # if any are not Canceled, timeout, error, or successful then
        # updateLightsheetDatabaseStatus
        updateDBStatesAndTimes(imageProcessingDB)
        submissionStatus = "success"
    except requests.exceptions.RequestException as e:
        print('Exception occured')
        submissionStatus = requests
        if not continueOrReparameterize:
            imageProcessingDB.jobs.remove({"_id": job_id})
    return submissionStatus


def stepOrTemplateNamePathMaker(stepOrTemplateName):
    if stepOrTemplateName.find("Step: ", 0, 6) != -1:
        stepOrTemplateName = url_for('workflow', step=stepOrTemplateName[6:])
    else:
        stepOrTemplateName = url_for('workflow', template=stepOrTemplateName[10:])
    return stepOrTemplateName

def copyStepInDatabase(imageProcessingDB, originalStepName, newStepName, newStepDescription = None):
    originalStep = list(imageProcessingDB.step.find({"name": originalStepName}, {'_id' : 0}))
    if originalStep:
        originalStep=originalStep[0]
        newStep = originalStep
        newStep["name"] = newStepName
        originalParameters=originalStep['parameter']
        newParameterIds = copyParameterInDatabase(imageProcessingDB, originalParameters, originalStepName, newStepName)
        if newStepDescription:
            newStep['Description'] = newStepDescription
        newStep['parameter'] = newParameterIds
        imageProcessingDB.step.insert_one(newStep)

def copyParameterInDatabase(imageProcessingDB, parameterIds, originalStepName, newStepName):
    newParameterIds = parameterIds
    for i,currentParameterId in enumerate(parameterIds):
        newParameter = list(imageProcessingDB.parameter.find({"_id": currentParameterId} , {'_id': 0}))[0]
        newParameter['name']=newParameter['name'].replace('_'+originalStepName, '_'+newStepName)
        textIndex = 1
        while textIndex<5 and newParameter["text"+str(textIndex)]:
            newParameter["text"+str(textIndex)] = newParameter["text"+str(textIndex)].replace('_'+originalStepName, '_'+newStepName)
            textIndex=textIndex+1
        #Insert new parameter and store Ids
        newParameterIds[i]=imageProcessingDB.parameter.insert_one(newParameter).inserted_id
        isGlobalParameter = ("globalparameters" in originalStepName.lower())
        if isGlobalParameter:
            field = 'inputField'
        else:
            field = 'outputField'
        dependencies = list(imageProcessingDB.dependency.find({field: currentParameterId} , {'_id': 1 }))
        if dependencies:
            dependencyIds = [d['_id'] for d in dependencies]
            copyDependenciesInDatabase(imageProcessingDB, dependencyIds, originalStepName, newStepName, field)
    return newParameterIds

def copyDependenciesInDatabase(imageProcessingDB, dependencyIds, originalStepName, newStepName, field):
    for currentDependencyId in dependencyIds:
        currentDependency = list(imageProcessingDB.dependency.find({"_id": currentDependencyId} , {'_id': 0}))[0]
        fieldName = list(imageProcessingDB.parameter.find({'_id': currentDependency[field]}))[0]['name']
        newFieldName = fieldName.replace('_'+originalStepName, '_'+newStepName)
        newFieldId = list(imageProcessingDB.parameter.find({'name': newFieldName} , {'_id':1}))[0]['_id']
        newDependency = currentDependency
        newDependency[field] = newFieldId
        newDependency['pattern'] = newDependency['pattern'].replace('_'+originalStepName, '_'+newStepName)
        imageProcessingDB.dependency.insert_one(newDependency)

def deleteStepAndReferencesFromDatabase(imageProcessingDB, stepName):
    step = list(imageProcessingDB.step.find({"name": stepName}))[0]
    stepId = step['_id']
    #delete from templates
    templatesReferencingStep = list(imageProcessingDB.template.find({"steps": step['_id']} ))
    if templatesReferencingStep:
        for templateReferencingStep in templatesReferencingStep:
            updatedSteps = templateReferencingStep['steps']
            updatedSteps.remove(stepId)
            imageProcessingDB.template.update_one({'_id': templateReferencingStep['_id']}, {'$set': {"steps" : updatedSteps}})
    #Delete parameters and dependencies based on it
    parameterIds = step['parameter']
    for currentParameterId in parameterIds:
        temp=1
        imageProcessingDB.dependency.remove({"outputField": currentParameterId})
        imageProcessingDB.parameter.remove({'_id': currentParameterId})
    #Delete step
    imageProcessingDB.step.remove({'_id': stepId})

