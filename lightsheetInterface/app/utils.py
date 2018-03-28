import numpy, datetime, glob, scipy, re, json, requests, os, ipdb
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from wtforms import *
from multiprocessing import Pool
from pprint import pprint
from scipy import misc
from datetime import datetime
from pytz import timezone
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from app.models import AppConfig, Step, Parameter
from app.settings import Settings

settings = Settings()

def getJobInfoFromDB(lightsheetDB, _id=None, parentOrChild="parent", getParameters=False):
  if _id:
    _id = ObjectId(_id)
    if parentOrChild=="parent":
      parentJobInfo = list(lightsheetDB.jobs.find({},{"steps":0}))
      for currentJobInfo in parentJobInfo:
        currentJobInfo.update({"selected":""})
        if currentJobInfo["_id"]==_id:
          currentJobInfo.update({"selected":"selected"})
      return parentJobInfo
    else:
      if getParameters:
        return list(lightsheetDB.jobs.find({"_id":_id}))
      else:
        return list(lightsheetDB.jobs.find({"_id":_id},{"steps.parameters":0}))
  else:
    return list(lightsheetDB.jobs.find({},{"steps":0}))

# Calculate properties of parameter based on its values (e.g. if number or text field has been filled in or which frequency / which range is selected)
def getType(parameter):
  frequent = []
  sometimes = []
  rare = []
  for param in parameter:
    if param.number1 != None:
      param.type = 'Number'
      if param.number2 == None:
        param.count = '1'
      elif param.number3 == None:
        param.count = '2'
      else:
        param.count = '3'
    else:
      param.type = 'Text'
      param.count = '1'

    if param.frequency == 'F':
      frequent.append(param)
    elif param.frequency == 'S':
      sometimes.append(param)
    elif param.frequency == 'R':
      rare.append(param)

  result = {'frequent': frequent, 'sometimes': sometimes, 'rare': rare}
  return result

def getParameters(parameter):
  frequent = {}
  sometimes = {}
  rare = {}
  for param in parameter:
    if param.number1 != None:
      param.type = 'Number'
      if param.number2 == None:
        param.count = '1'
      elif param.number3 == None:
        param.count = '2'
      else:
        param.count = '3'
    else:
      param.type = 'Text'
      param.count = '1'

    if param.frequency == 'F':
      frequent[param.name] = param
    elif param.frequency == 'S':
      sometimes[param.name] = param
    elif param.frequency == 'R':
      rare[param.name] = param

  result = {'frequent': frequent, 'sometimes': sometimes, 'rare': rare}
  return result  

def buildConfigObject():
  try:
    steps = Step.objects.all().order_by('order')
    p = Parameter.objects.all()
    parameters = getType(p)
    paramDict = getParameters(p)
    config = {'steps': steps, 'parameter': parameters, 'parameterDictionary': paramDict}
  except ServerSelectionTimeoutError:
    return 404
  return config


def writeToJSON(name, value):
  result = None;
  if value == None:
    result = "\"_ArrayType_\":\"double\",\"_ArraySize_\":[0,0],\"_ArrayData_\":null"
  elif isinstance(value, list):
    print(result)
  elif isinstance(value, (int, long, float, complex)):
    result = "\"" + name + "\":" + value,
  elif value in 'xyz':
    print(result)
  else:
    print(result)

  return result


# Header for post request
def getHeaders(forQuery=False):
  if forQuery:
    return {'content-type': 'application/json', 'USERNAME': settings.username}
  else:
    return {'content-type': 'application/json', 'USERNAME': settings.username, 'RUNASUSER': 'lightsheet'}


# Timezone for timings
eastern = timezone('US/Eastern')
UTC = timezone('UTC')

def getJobInfoFromDB(lightsheetDB, _id=None, parentOrChild="parent", getParameters=False):
  if _id:
    _id = ObjectId(_id)
    if parentOrChild=="parent":
      parentJobInfo = list(lightsheetDB.jobs.find({},{"steps":0}))
      for currentJobInfo in parentJobInfo:
        currentJobInfo.update({"selected":""})
        if currentJobInfo["_id"]==_id:
          currentJobInfo.update({"selected":"selected"})
      return parentJobInfo
    else:
      if getParameters:
        return list(lightsheetDB.jobs.find({"_id":_id}))
      else:
        return list(lightsheetDB.jobs.find({"_id":_id},{"steps.parameters":0}))
  else:
    return list(lightsheetDB.jobs.find({},{"steps":0}))

def getJobStepData(_id, mongoClient):
  result = getConfigurationsFromDB(_id, mongoClient, stepName=None)
  if result != None and result != 404 and len(result) > 0 and 'steps' in result[0]:
    return result[0]['steps']
  return None

def getConfigurationsFromDB2(_id, mongoClient, stepName=None):
  result = None
  lightsheetDB = mongoClient.lightsheet
  if _id == "templateConfigurations":
    jobSteps = list(lightsheetDB.templateConfigurations.find({}, {'_id': 0, 'steps': 1}))
  else:
    jobSteps = list(lightsheetDB.jobs.find({'_id': ObjectId(_id)}, {'_id': 0, 'steps': 1}))

  if jobSteps:
    jobStepsList = jobSteps[0]["steps"]
    if stepName is not None:
      stepDictionary = next((dictionary for dictionary in jobStepsList if dictionary["name"] == stepName), None)
      if stepDictionary is not None:
        return stepDictionary["parameters"]
  return None

def getConfigurationsFromDB(_id, client, stepName=None):
  lightsheetDB = client.lightsheet
  if stepName:
    if _id=="templateConfigurations":
        output = list(lightsheetDB.templateConfigurations.find({'steps.name':stepName}, {'_id':0,"steps.$.parameters":1}))
    else:
        output = list(lightsheetDB.jobs.find({'_id':ObjectId(_id),'steps.name':stepName},{'_id':0,"steps.$.parameters":1}))
    if output:
        output=output[0]["steps"][0]["parameters"]
  else:
    if _id=="templateConfigurations":
        output = list(lightsheetDB.templateConfigurations.find({}, {'_id':0,'steps':1}))
    else:
        output = list(lightsheetDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'steps':1}))
  if output:
    return output
  else:
    return 404

def updateDBStatesAndTimes(lightsheetDB):
  allJobInfoFromDB = list(lightsheetDB.jobs.find())
  for parentJobInfoFromDB in allJobInfoFromDB:
    if parentJobInfoFromDB["state"] not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
      parentJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                                  params={'service-id':  parentJobInfoFromDB["jacs_id"]},
                                                  headers=getHeaders(True)).json()
      if parentJobInfoFromJACS and len(parentJobInfoFromJACS["resultList"]) > 0:
        parentJobInfoFromJACS = parentJobInfoFromJACS["resultList"][0]
        lightsheetDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"]},
                                     {"$set": {"state":parentJobInfoFromJACS["state"] }})
        allChildJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                            params={'parent-id': parentJobInfoFromDB["jacs_id"]},
                                            headers=getHeaders(True)).json()
        allChildJobInfoFromJACS = allChildJobInfoFromJACS["resultList"]
        if allChildJobInfoFromJACS:
          for currentChildJobInfoFromDB in parentJobInfoFromDB["steps"]:
            if currentChildJobInfoFromDB["state"] not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']: #need to update step
              currentChildJobInfoFromJACS = next((step for step in allChildJobInfoFromJACS if step["args"][1] == currentChildJobInfoFromDB["name"]),None)
              if currentChildJobInfoFromJACS:
                creationTime = convertJACStime(currentChildJobInfoFromJACS["processStartTime"])
                outputPath = "N/A"
                if "outputPath" in currentChildJobInfoFromJACS:
                  outputPath = currentChildJobInfoFromJACS["outputPath"][:-11]

                lightsheetDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"],"steps.name": currentChildJobInfoFromDB["name"]},
                                             {"$set": {"steps.$.state":currentChildJobInfoFromJACS["state"],
                                                       "steps.$.creationTime": creationTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                       "steps.$.elapsedTime":str(datetime.now(eastern)-creationTime),
                                                       "steps.$.logAndErrorPath":outputPath
                                                     }})
              
                if currentChildJobInfoFromJACS["state"] in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
                  endTime = convertJACStime(currentChildJobInfoFromJACS["modificationDate"])
                  lightsheetDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"],"steps.name": currentChildJobInfoFromDB["name"]},
                                               {"$set": {"steps.$.endTime": endTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                         "steps.$.elapsedTime": str(endTime-creationTime)
                                                       }})
  
def convertJACStime(t):
   t=datetime.strptime(t[:-9], '%Y-%m-%dT%H:%M:%S')
   t=UTC.localize(t).astimezone(eastern)
   return t

def convertArrayFieldValue(stringValue):
  stringValue = stringValue.replace("{","") #remove cell formatting
  stringValue = stringValue.replace("}","")
  stringValue = stringValue.replace(" ",",") #replace commas with spaces
  #stringValue = ' '.join(stringValue.split()) #make sure everything is singlespaced
  #stringValue = stringValue.replace(" ",",") #replace spaces by commas
  stringValue = re.sub(',,+' , ',', stringValue) #replace two or more commas with single comma
  #lots of substitutions to have it make sense. First get rid of extra commas
  #Then get rid of semicolon-comma pairs
  #Then make sure arrays are separated properly
  #Finally add brackets to the beginning/end if necessary
  stringValue = re.sub('\[,' , '[', stringValue) 
  stringValue = re.sub(',\]' , ']', stringValue)
  stringValue = re.sub(';,' , ';', stringValue)
  stringValue = re.sub(',;' , ';', stringValue)
  stringValue = re.sub('\];\[' , '],[', stringValue)
  stringValue = re.sub(';', '],[', stringValue)
  if '],[' in stringValue:
    stringValue = "[" + stringValue + "]"
  return 

def getParentServiceDataFromJACS(lightsheetDB, serviceIndex=None):
    #Function to get information about parent jobs from JACS database marks currently selected job
    allJACSids = list(lightsheetDB.jobs.find({},{'_id':0, 'jacs_id': 1}))
    allJACSids = [str(dictionary['jacs_id']) if 'jacs_id' in dictionary.keys() else "" for dictionary in allJACSids]
    requestOutputJsonified = [requests.get(settings.devOrProductionJACS+'/services/',
                                           params={'service-id':  JACSid},
                                           headers=getHeaders(True)).json()
                              for JACSid in allJACSids]
    serviceData = []
    count=0
    for jobInformation in requestOutputJsonified:
      if jobInformation['resultList'] is not None and len(jobInformation['resultList']) > 0:
        jobInformationResultListDictionary = jobInformation['resultList'][0]
        jobInformationResultListDictionary.update((k,str(convertEpochTime(v))) for k, v in jobInformationResultListDictionary.items() if k=="creationDate")
        jobInformationResultListDictionary["selected"]=''
        jobInformationResultListDictionary["index"] = str(count)
        serviceData.append(jobInformationResultListDictionary)
        count=count+1

        # serviceData = [dictionary['resultList'][0] for dictionary in requestOutputJsonified]
    if serviceData and serviceIndex is not None:
      serviceData[int(serviceIndex)]["selected"] = 'selected'

    return serviceData

def getChildServiceDataFromJACS(parentId):
    #Function to get information from JACS service databases
    #Gets information about currently running and already completed jobs
    requestOutput = requests.get(settings.devOrProductionJACS+'/services/',
                                 params={'parent-id': str(parentId)},
                                 headers=getHeaders(True)).json()
    serviceData=requestOutput['resultList']
    for dictionary in serviceData: #convert date to nicer string
         dictionary.update((k,convertEpochTime(v)) for k, v in dictionary.items() if (k=="creationDate" or k=="modificationDate") )
    serviceData = requestOutputJsonified['resultList']
    serviceData = sorted(serviceData, key=lambda k: k['creationDate'])
    return serviceData



def convertEpochTime(v):
  if type(v) is str:
    return v
  else:
    return datetime.fromtimestamp(int(v) / 1000, eastern)


def insertImage(camera, channel, plane):
  imagePath = path + 'SPC' + specimenString + '_TM' + timepointString + '_ANG000_CM' + camera + '_CHN' + channel.zfill(
    2) + '_PH0_PLN' + str(plane).zfill(4) + '.tif'
  return misc.imread(imagePath)


def generateThumbnailImages(path, timepoint, specimen, cameras, channels, specimenString, timepointString):
  # path = sys.argv[1]
  # timepoint = sys.argv[2]
  # specimen = sys.argv[3]
  # cameras = sys.argv[4].split(',')
  # channels = sys.argv[5].split(',')
  # specimenString = specimen.zfill(2)
  # timepointString = timepoint.zfill(5)
  # path = path+'/SPM' + specimenString + '/TM' + timepointString + '/ANG000/'

  pool = Pool(processes=32)
  numberOfChannels = len(channels)
  numberOfCameras = len(cameras)
  # fig, ax = plt.subplots(nrows = numberOfChannels, ncols = 2*numberOfCameras)#, figsize=(16,8))
  fig = plt.figure();
  fig.set_size_inches(16, 8)
  outer = gridspec.GridSpec(numberOfChannels, numberOfCameras, wspace=0.3, hspace=0.3)

  for channelCounter, channel in enumerate(channels):
    for cameraCounter, camera in enumerate(cameras):
      inner = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer[cameraCounter, channelCounter], wspace=0.1,
                                               hspace=0.1)
      newList = [(camera, channel, 0)]
      numberOfPlanes = len(glob.glob1(path, '*CM' + camera + '_CHN' + channel.zfill(2) + '*'))
      for plane in range(1, numberOfPlanes):
        newList.append((camera, channel, plane))

      images = pool.starmap(insertImage, newList)
      images = numpy.asarray(images).transpose(1, 2, 0)
      xy = numpy.amax(images, axis=2)
      xz = numpy.amax(images, axis=1)
      ax1 = plt.Subplot(fig, inner[0])
      ax1.imshow(xy, cmap='gray')
      fig.add_subplot(ax1)
      ax1.axis('auto')
      ax2 = plt.Subplot(fig, inner[1])
      ax2.imshow(xz, cmap='gray')
      fig.add_subplot(ax2)
      ax2.axis('auto')
      ax2.get_yaxis().set_visible(False)
      # ax1.get_shared_y_axes().join(ax1, ax2)
      baseString = 'CM' + camera + '_CHN' + channel.zfill(2)
      ax1.set_title(baseString + ' xy')  # , fontsize=12)
      ax2.set_title(baseString + ' xz')  # , fontsize=12)

  fig.savefig(url_for('static', filename='img/test.jpg'))
  pool.close()


def getPipelineStepNames():
  steps = Step.objects.all().order_by('order')
  names = []
  for step in steps:
    names.append(step.name)
  return names

def loadParameters(fileName):
  with open(fileName) as data_file:
    data = json.load(data_file)
    parseJsonData(data)

def parseJsonData(data, stepName):
  config = buildConfigObject()
  class F(Form):
    pass

  class S(Form):
    pass

  class R(Form):
    pass

  keys = None
  if type(data) is list and len(data) > 0 and data[0]['parameters'] != None:
    parameterData = data[0]['parameters']
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

      # build the result form object with forms for each frequency
      forms = {}
      forms['frequent'] = formInstances[0]
      forms['sometimes'] = formInstances[1]
      forms['rare'] = formInstances[2]
      return forms
  return None

def loadJobDataFromLocal(mydir):
  files = os.listdir(mydir)
  for filename in files:
    file = mydir + '/' + filename
    with open(file, 'r') as f:
      data = json.load(f)
      return data

def getAppVersion(path):
  mpath = path.split('/')
  result = '/'.join(mpath[0:(len(mpath) - 1)]) + '/package.json'
  with open(result) as package_data:
    data = json.load(package_data)
    package_data.close()
    return data['version']


def trimStepName(name):
  return name.split('_',1)[0]