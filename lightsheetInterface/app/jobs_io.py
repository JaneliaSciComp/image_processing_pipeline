# Contains functons to load jobs and submit jobs
import re, ipdb, json
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
            range = True
          parameter = splitRest[0]
        if range:
          if parameter in stepParamResult:
            paramValueSet = stepParamResult[parameter] # get the existing object
          else:
            paramValueSet = {} # create a new object
          # move the parts of the range parameter to the right key of the object
          if splitRest[1] == 'start':
            paramValueSet['start'] = float(postedData[step][parameterKey]) if postedData[step][parameterKey] is not '' else ''
          elif splitRest[1] == 'end':
            paramValueSet['end'] = float(postedData[step][parameterKey]) if postedData[step][parameterKey] is not '' else ''
          elif splitRest[1] == 'every':
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
          if re.match("[-+]?[0-9]*\.?[0-9]*.$", currentValue) is None: # no float
            try:
              tmp = json.loads(currentValue)
              paramValueSet.append(tmp)
            except ValueError:
              paramValueSet.append(currentValue)
          else: # it's actual a float value -> get the value
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