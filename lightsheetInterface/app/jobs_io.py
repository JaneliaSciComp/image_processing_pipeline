# Contains functons to load jobs and submit jobs
import re, ipdb, json
from logging.config import dictConfig
from mongoengine.queryset.visitor import Q
from app.models import AppConfig, Step, Parameter, Template
from pprint import pprint
from enum import Enum
from app import app
from app.settings import Settings
from app.utils import submitToJACS, getJobStepData, stepOrTemplateNamePathMaker
from bson.objectid import ObjectId

class ParameterTypes(Enum):
  checkbox = 1
  rangeParam = 2
  flag = 3
  option = 4

# change data before job is resubmitted
def reformatDataToPost(postedData):
  result = []
  p = 'parameters'
  if postedData and postedData != {}:
    for step in postedData.keys():
      # first part: get the parameter values into lists
      stepResult = {}
      stepResult['name'] = step

      # add some optional paramters
      if 'type' in postedData[step].keys():
        stepResult['type'] = postedData[step]['type']

      if 'bindPaths' in postedData[step].keys():
        stepResult['bindPaths'] = postedData[step]['bindPaths']

      stepResult['state'] = 'NOT YET QUEUED'
      stepParamResult = {}
      sortedParameters = sorted(postedData[step][p].keys())
      checkboxes = []
      for parameterKey in sortedParameters:
        # Find checkboxes and deal with them separately
        if 'checkbox' in parameterKey:
          checkboxes.append(parameterKey);
        paramType= None
        range = False

        q = Parameter.objects.filter(Q(formatting='F') & (Q(name=parameterKey.split('-')[0]) | Q(name= parameterKey.split('-')[0] + '_' + step )))
        if (len(q) != 0): # this parameter is a range parameter
          paramType = ParameterTypes.flag

        # First test if it's a nested parameter
        if '-' in parameterKey: # check, whether this is a range parameter
          splitRest = parameterKey.split('-')
          q = Parameter.objects.filter(Q(formatting='R') & (Q(name=parameterKey.split('-')[0]) | Q(name= parameterKey.split('-')[0] + '_' + step )))
          if (len(q) != 0): # this parameter is a range parameter
            paramType = ParameterTypes.rangeParam
            range = True

        # Then check if stepname is part of parameter name
        if '_' in parameterKey:
          # TODO: check, if part after underscore is really a step name or _ part of parameter name
          split = parameterKey.split('_')
          parameter = split[0]
        else:
          parameter = parameterKey;
        #parameter = parameter.split('-')[0]

        rangeParam = False
        if paramType and paramType == ParameterTypes.rangeParam:
          rangeParam = True
          if parameter in stepParamResult:
            paramValueSet = stepParamResult[parameter] # get the existing object
          else:
            paramValueSet = {} # create a new object
          # move the parts of the range parameter to the right key of the object
          if splitRest[1] == 'start' or splitRest[1] == 'end' or splitRest[1] == 'every':
            currValue = postedData[step][p][parameterKey]
            if currValue == "empty":
              rangeParam = False
            else :
              if splitRest[1] == 'start':
                paramValueSet['start'] = float(currValue) if currValue is not '' and currValue != "[]" else ''
              elif splitRest[1] == 'end':
                paramValueSet['end'] = float(currValue) if currValue is not '' and currValue != "[]" else ''
              elif splitRest[1] == 'every':
               paramValueSet['every'] = float(currValue) if currValue is not '' and currValue != "[]" else ''
          if rangeParam:
            # update the object
            stepParamResult[parameter] = paramValueSet

        if not rangeParam: # no range
          if parameter in stepParamResult:
            paramValueSet = stepParamResult[parameter]
          else:
            paramValueSet = []
          if not paramValueSet:
            paramValueSet = []
          stepParamResult[parameter] = paramValueSet

          # if paramType and paramType == ParameterTypes.flag:
            #TODO: 'cope with flag parameters when submitting the job'

          # check if current value is a float within a string and needs to be converted
          currentValue = postedData[step][p][parameterKey]
          if re.match("[-+]?[0-9]*\.?[0-9]*.$", currentValue) is None: # no float
            try:
              tmp = json.loads(currentValue)
              paramValueSet.append(tmp)
            except ValueError:
              paramValueSet.append(currentValue)
          else: # it's actual a float value -> get the value
              paramValueSet.append(float(currentValue))

      checkboxesClean = []
      for param in checkboxes:
        if postedData[step][p][param] == 'true':
          checkboxesClean.append(param.split('-')[1].split('_')[0])

      if 'emptycheckbox' in stepParamResult.keys():
        stepParamResult.pop('emptycheckbox')

      # cleanup step / second part: for lists with just one element, get the element
      for param in stepParamResult:
        if param in checkboxesClean:
          stepParamResult[param] = []
        else:
          if type(stepParamResult[param]) is list:
            if len(stepParamResult[param]) == 1:
              stepParamResult[param] = stepParamResult[param][0]
            else:
              for elem in stepParamResult[param]:
                if elem == "" and len(set(stepParamResult[param])) == 1:
                 stepParamResult[param] = []
                 break;
      stepResult['parameters'] = stepParamResult
      result.append(stepResult)
  return result

# new parse data, don't create any flask forms
def parseJsonDataNoForms(data, stepName, config):
  # Check structure of incoming data
  if 'parameters' in data:
    parameterData = data['parameters']
  else:
    parameterData = data
  keys = parameterData.keys()
  if keys != None:
    pFrequent = {}
    pSometimes = {}
    pRare = {}
    # For each key, look up the parameter type and add parameter to the right type of form based on that:
    for key in keys:
      param = Parameter.objects.filter(name=key).first()
      if param == None: # key doesn't exist, try extended key
        extendedKey = key + "_" + stepName
        param = Parameter.objects.filter(name=extendedKey).first()
      if param != None: # check if key now exists
        if type(parameterData[key]) is list and len(parameterData[key]) == 0:
          parameterData[key] = ''
        elif parameterData[key] == 'None':
          parameterData[key] = ''
        if param.frequency == 'F':
          pFrequent[key] =  {}
          if key in config['parameterDictionary']['frequent'].keys():
            pFrequent[key]['config'] = config['parameterDictionary']['frequent'][key]
          else:
            pFrequent[key]['config'] = config['parameterDictionary']['frequent'][key + '_' + stepName]
          pFrequent[key]['data'] = parameterData[key]
        elif param.frequency == 'S':
          pSometimes[key] = {}
          if key in config['parameterDictionary']['sometimes'].keys():
            pSometimes[key]['config'] = config['parameterDictionary']['sometimes'][key]
          else:
            pSometimes[key]['config'] = config['parameterDictionary']['sometimes'][key + '_' + stepName]
          pSometimes[key]['data'] = parameterData[key]
        elif param.frequency == 'R':
          pRare[key] = {}
          # Either look up value of key itself or for the extended key with the stepname and store it into result object
          if key in config['parameterDictionary']['rare'].keys():
            pRare[key]['config'] = config['parameterDictionary']['rare'][key]
          else:
            pRare[key]['config'] = config['parameterDictionary']['rare'][key + '_' + stepName]
          pRare[key]['data'] = parameterData[key]

  result = {}
  result['frequent'] = pFrequent
  result['sometimes'] = pSometimes
  result['rare'] = pRare
  return result


#If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
def doThePost(formJson, reparameterize, imageProcessingDB, imageProcessingDB_id, submissionAddress = None, stepOrTemplateName = None):
  app.logger.info('Post json data: {0}'.format(formJson))
  app.logger.info('Current Step Or Template: {0}'.format(stepOrTemplateName))
  settings = Settings()

  if formJson != '[]' and formJson != None:
      userDefinedJobName=[]

      # get the name of the job first
      jobName = ''
      if 'jobName' in formJson.keys():
        jobName = formJson['jobName']
        del(formJson['jobName'])

      # delete the jobName entry from the dictionary so that the other entries are all steps
      jobSteps = list(formJson.keys())

      processedDataTemp = reformatDataToPost(formJson)
      app.logger.info(processedDataTemp)
      globalParametersPosted = next((step["parameters"] for step in processedDataTemp if step["name"]=="globalParameters"),None)
      processedData=[]
      remainingStepNames=[];
      allSteps = Step.objects.all().order_by('order')
      if allSteps:
        for step in allSteps:
          currentStepDictionary = next((dictionary for dictionary in processedDataTemp if dictionary["name"] == step.name), None)
          if currentStepDictionary:
              if step.submit:
                remainingStepNames.append(currentStepDictionary["name"])
              processedData.append(currentStepDictionary)

      # Prepare the db data
      dataToPostToDB = {"jobName": jobName,
                        "submissionAddress": submissionAddress,
                        "stepOrTemplateName": stepOrTemplateName,
                        "state": "NOT YET QUEUED",
                        "containerVersion":"placeholder",
                        "remainingStepNames":remainingStepNames,
                        "steps": processedData
                       }

      # Insert the data to the db
      if reparameterize:
        imageProcessingDB_id=ObjectId(imageProcessingDB_id)
        subDict = {k: dataToPostToDB[k] for k in ('jobName', 'submissionAddress', 'stepOrTemplateName', 'state', 'containerVersion', 'remainingStepNames')}
        imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": subDict})
        for currentStepDictionary in processedData:
          imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id,"steps.name": currentStepDictionary["name"]},{"$set": {"steps.$":currentStepDictionary}})
      else:
        imageProcessingDB_id = imageProcessingDB.jobs.insert_one(dataToPostToDB).inserted_id

      if globalParametersPosted:
        globalParametersPosted.pop("")
        imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": {"globalParameters":globalParametersPosted}})
      submissionStatus = submitToJACS(imageProcessingDB, imageProcessingDB_id, reparameterize)

def loadPreexistingJob(imageProcessingDB, imageProcessingDB_id, reparameterize, configObj):
  submissionStatus = None

  pipelineSteps = {}
  jobData =  getJobStepData(imageProcessingDB_id, imageProcessingDB) # get the data for all jobs
  ableToReparameterize=True
  succededButLatterStepFailed=[]

  if jobData:
    globalParametersAndRemainingStepNames = list(imageProcessingDB.jobs.find({"_id":ObjectId(imageProcessingDB_id)},{"remainingStepNames":1,"globalParameters":1}))
    if "globalParameters" in globalParametersAndRemainingStepNames[0]:
      globalParameters = globalParametersAndRemainingStepNames[0]["globalParameters"]
    if ("pause" in jobData[-1]["parameters"] and jobData[-1]["parameters"]["pause"]==0 and jobData[-1]["state"]=="SUCCESSFUL") or any( (step["state"] in "RUNNING CREATED") for step in jobData):
      ableToReparameterize=False
    errorStepIndex = next((i for i,step in enumerate(jobData) if step["state"]=="ERROR"),None)
    if errorStepIndex:
      for i in range(errorStepIndex):
        succededButLatterStepFailed.append(jobData[i]["name"])
  if reparameterize=="true" and imageProcessingDB_id:
    reparameterize=True
    remainingStepNames=globalParametersAndRemainingStepNames[0]["remainingStepNames"]
    if not ableToReparameterize:
      abort(404)
  else:
    reparameterize=False

  # match data on step name
  matchNameIndex = {}
  if type(jobData) is list:
    if imageProcessingDB_id != None: # load data for an existing job
      for i in range(len(jobData)):
        if 'name' in jobData[i]:
          matchNameIndex[jobData[i]['name']] = i
      # go through all steps and find those, which are used by the current job
      for currentStep in matchNameIndex.keys():
        step = Step.objects(name=currentStep).first()
        editState = 'enabled'
        checkboxState = 'checked'
        collapseOrShow = 'show'
        stepData = jobData[matchNameIndex[currentStep]]
        if (reparameterize and (currentStep not in remainingStepNames)) or (currentStep in succededButLatterStepFailed):
          editState = 'disabled'
          checkboxState = 'unchecked'
          collapseOrShow = ''
        if stepData:
          jobs = parseJsonDataNoForms(stepData, currentStep, configObj)
          # Pipeline steps is passed to index.html for formatting the html based
          pipelineSteps[currentStep] = {
            'stepName': currentStep,
            'stepDescription': step.description,
            'inputJson': None,
            'state': editState,
            'checkboxState': checkboxState,
            'collapseOrShow': collapseOrShow,
            'jobs': jobs
          }
  elif type(jobData) is dict:
    submissionStatus = 'Job cannot be loaded.'

  return pipelineSteps, submissionStatus