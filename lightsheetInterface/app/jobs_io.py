# Contains functons to load jobs and submit jobs
import re, ipdb, json
from logging.config import dictConfig
from mongoengine.queryset.visitor import Q
from app.models import AppConfig, Step, Parameter, Template
from pprint import pprint
from enum import Enum
from app import app
from app.settings import Settings
from app.utils import submitToJACS

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

        if paramType and paramType == ParameterTypes.rangeParam:
          if parameter in stepParamResult:
            paramValueSet = stepParamResult[parameter] # get the existing object
          else:
            paramValueSet = {} # create a new object
          # move the parts of the range parameter to the right key of the object
          if splitRest[1] == 'start':
            paramValueSet['start'] = float(postedData[step][p][parameterKey]) if postedData[step][p][parameterKey] is not '' else ''
          elif splitRest[1] == 'end':
            paramValueSet['end'] = float(postedData[step][p][parameterKey]) if postedData[step][p][parameterKey] is not '' else ''
          elif splitRest[1] == 'every':
            paramValueSet['every'] = float(postedData[step][p][parameterKey]) if postedData[step][p][parameterKey] is not '' else ''
          # update the object
          stepParamResult[parameter] = paramValueSet
        else: # no range
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
def doThePost(formJson, reparameterize, imageProcessingDB, imageProcessingDB_id, submissionAddress, currentTemplate = None):
  app.logger.info('Post json data: {0}'.format(formJson))
  app.logger.info('Current template: {0}'.format(currentTemplate))
  settings = Settings()

  if formJson != '[]' and formJson != None:
      userDefinedJobName=[]

      # get the name of the job first
      jobName = formJson['jobName']
      del(formJson['jobName'])

      # delete the jobName entry from the dictionary so that the other entries are all steps
      jobSteps = list(formJson.keys())

      processedDataTemp = reformatDataToPost(formJson)
      globalParametersPosted = next((step["parameters"] for step in processedDataTemp if step["name"]=="globalParameters"),None)
      processedData=[]
      remainingStepNames=[];
      allSteps = Step.objects.all()
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
                        "state": "NOT YET QUEUED",
                        "containerVersion":"placeholder",
                        "remainingStepNames":remainingStepNames,
                        "steps": processedData
                       }

      # Insert the data to the db
      if reparameterize:
        imageProcessingDB_id=ObjectId(imageProcessingDB_id)
        subDict = {k: dataToPostToDB[k] for k in ('jobName', 'submissionAddress', 'state', 'containerVersion', 'remainingStepNames')}
        imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": subDict})
        for currentStepDictionary in processedData:
          imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id,"steps.name": currentStepDictionary["name"]},{"$set": {"steps.$":currentStepDictionary}})
      else:
        imageProcessingDB_id = imageProcessingDB.jobs.insert_one(dataToPostToDB).inserted_id

      if globalParametersPosted:
        globalParametersPosted.pop("")
        imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": {"globalParameters":globalParametersPosted}})
      submissionStatus = submitToJACS(imageProcessingDB, imageProcessingDB_id, reparameterize)