# Contains functons to load jobs and submit jobs
import re, ipdb
from mongoengine.queryset.visitor import Q
from app.models import AppConfig, Step, Parameter
from pprint import pprint

# change data before job is resubmitted
def reformatDataToPost(postedData):
  result = []
  if postedData and postedData != {}:
    for step in postedData.keys():
      # first part: get the parameter values into lists
      stepResult = {}
      stepResult['name'] = step
      stepResult['state'] = 'NOT YET QUEUED'
      stepParamResult = {}
      sortedParameters = sorted(postedData[step].keys())
      for parameterKey in sortedParameters:
        range = False
        if '_' in parameterKey:
          # TODO: check, if part after underscore is really a step name or _ part of parameter name
          split = parameterKey.split('_')
          parameter = split[0]
          rest = split[1]
        else:
          parameter = parameterKey;
          rest = parameterKey
        if '-' in parameter: # check, whether this is a range parameter
          splitRest = parameter.split('-')
          q = Parameter.objects.filter(Q(formatting='R') & (Q(name=parameterKey.split('-')[0]) | Q(name= parameterKey.split('-')[0] + '_' + step )))
          if (len(q) != 0): # this parameter is a range parameter
            parameter = splitRest[0]
            range = True
          else: # this parameter is a range parameter
            parameter = splitRest[0]
        if range:
          if parameter in stepParamResult:
            paramValueSet = stepParamResult[parameter] # get the existing object
          else:
            paramValueSet = {} # create a new object
          # move the parts of the range parameter to the right key of the object
          if splitRest[1] == '0':
            paramValueSet['start'] = float(postedData[step][parameterKey]) if postedData[step][parameterKey] is not '' else ''
          elif splitRest[1] == '1':
            paramValueSet['end'] = float(postedData[step][parameterKey]) if postedData[step][parameterKey] is not '' else ''
          elif splitRest[1] == '2':
            paramValueSet['every'] = float(postedData[step][parameterKey]) if postedData[step][parameterKey] is not '' else ''
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

          # check if current value is a float within a string and needs to be converted
          currentValue = postedData[step][parameterKey]
          if re.match("[-+]?[0-9]*\.?[0-9]*.$", currentValue) is None:
            paramValueSet.append(currentValue)
          else:
            # it's actual a float value -> get the value
            paramValueSet.append(float(currentValue))

      # cleanup step / second part: for lists with just one element, get the element
      for param in stepParamResult:
        if type(stepParamResult[param]) is list and len(stepParamResult[param]) == 1:
          stepParamResult[param] = stepParamResult[param][0]
      stepResult['parameters'] = stepParamResult
      result.append(stepResult)
  return result

# new parse data, don't create any flask forms
def parseJsonDataNoForms(data, stepName, config):
  #ipdb.set_trace()
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

# parse data for existing job and create forms
def parseJsonData(data, stepName, config):
  class F(Form):
    pass

  class S(Form):
    pass

  class R(Form):
    pass

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
      if param == None:
        extendedKey = key + "_" + stepName
        param = Parameter.objects.filter(name=extendedKey).first()
      if param != None:
        if param.frequency == 'F':
          pFrequent[key] = parameterData[key]
        elif param.frequency == 'S':
          pSometimes[key] = parameterData[key]
        elif param.frequency == 'R':
          pRare[key] = parameterData[key]

    keyList = []
    formClassList = []

    keyList.append(pFrequent.keys())
    keyList.append(pSometimes.keys())
    keyList.append(pRare.keys())

    formClassList.append(F)
    formClassList.append(S)
    formClassList.append(R)

    length = len(keyList) # make sure formList matches keyList
    saveRangeKeys = []
    saveArrays = []
    for i in range(0, length):
      tmpKeys = keyList[i]
      for k in tmpKeys:
        if i == 0:
          configParamDict = config['parameterDictionary']['frequent']
        elif i == 1:
          configParamDict = config['parameterDictionary']['sometimes']
        elif i == 2:
          configParamDict = config['parameterDictionary']['rare']
        configParam = None
        if k in configParamDict.keys():
          configParam = configParamDict[k]
        elif (k + '_' + stepName) in configParamDict.keys():
          configParam = configParamDict[k + '_' + stepName]
        if configParam != None:
          if configParam.type == 'Number':
            if configParam.formatting == "R":
              setattr(formClassList[i], k, FieldList(TextField('')))
              saveRangeKeys.append((i,k))
            elif type(parameterData[k]) is list:
              setattr(formClassList[i], k, FieldList(TextField('')))
              saveArrays.append((i,k))
            else:
              setattr(formClassList[i], k, FloatField(k, default=parameterData[k]))
          elif configParam.type == 'Text':
            data = parameterData[k]
            if type(data) is dict and '_ArrayData_' in data and data['_ArrayData_'] == None:
              if data['_ArraySize_'] == [0,0]:
                setattr(formClassList[i], k, FieldList(FloatField('')))
                saveArrays.append((i,k))
              else:
                setattr(formClassList[i], k, TextField(k, default=None))
            else:
              setattr(formClassList[i], k, TextField(k, default=parameterData[k]))

    # create instances for each form
    formInstances = []
    formInstances.append(formClassList[0]())
    formInstances.append(formClassList[1]())
    formInstances.append(formClassList[2]())

    # fill the special range fields with default values
    for i,j in saveRangeKeys:
      rangeData = parameterData[j]
      if type(rangeData) is dict:
        formInstances[i][j].append_entry(rangeData['start'])
        formInstances[i][j].append_entry(rangeData['end'])
        formInstances[i][j].append_entry(rangeData['every'])
        formInstances[i][j].entries[0].label = 'From: '
        formInstances[i][j].entries[1].label = 'To: '
        formInstances[i][j].entries[2].label = 'Every: '

    # fill the special array fields with default values
    for i,j in saveArrays:
      arrayData = parameterData[j]
      if type(arrayData) is list:
        for l in arrayData:
          formInstances[i][j].append_entry(l)
      if type(arrayData) is dict:
        formInstances[i][j].append_entry()
        formInstances[i][j].append_entry()

    # build the result form object with forms for each frequency
    forms = {}
    forms['frequent'] = formInstances[0]
    forms['sometimes'] = formInstances[1]
    forms['rare'] = formInstances[2]
    return forms
  return None