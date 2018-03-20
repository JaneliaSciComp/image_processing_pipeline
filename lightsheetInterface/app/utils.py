import sys, numpy, datetime, glob, scipy, re, json, requests, os, ipdb
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pymongo import MongoClient
from bson.objectid import ObjectId
from wtforms import Form, StringField, validators
from mongoengine.queryset.visitor import Q
from pylab import figure, axes, pie, title, show
from multiprocessing import Pool
from pprint import pprint
from scipy import misc
from datetime import datetime
from pytz import timezone
from app.models import AppConfig, Step, Parameter
from app.forms import StepForm
from app.settings import Settings

settings = Settings()

def testDatabaseStatus(db):
  # Issue the serverStatus command and print the results
  serverStatusResult=db.command("serverStatus")

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

def buildConfigObject():
  steps = Step.objects.all().order_by('order')
  parameter = Parameter.objects.all()
  paramNew = getType(parameter)

  config = {'steps': steps, 'parameter': paramNew}
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

#Header for post request
def getHeaders(forQuery=False):
  if forQuery:
    return {'content-type': 'application/json', 'USERNAME': settings.username}
  else:
    return {'content-type': 'application/json', 'USERNAME': settings.username, 'RUNASUSER': 'lightsheet'}

#Timezone for timings
eastern = timezone('US/Eastern')
UTC = timezone('UTC')

def getJobInfoFromDB(lightsheetDB, _id=None):
  if _id:
    return list(lightsheetDB.jobs.find({"_id":ObjectId(_id)}))
  else:
    return list(lightsheetDB.jobs.find({},{"steps":0}))
      

def getAllJobInfoFromDB(lightsheetDB, jobIndex=None):
    allJobInfo = list(lightsheetDB.jobs.find())
    jobSelected = False
    parentJobInfo = []
    for count, currentJobInfo in enumerate(allJobInfo):
        currentJobInfo["selected"]='';
        currentJobInfo["index"]=str(count)
        
        currentParentJobInfo = {"creationDate": currentJobInfo["creationDate"], 
                                "selectedStepNames":currentJobInfo["selectedStepNames"],
                                "name":currentJobInfo["name"],
                                "configAddress":currentJobInfo["configAddress"]}
        parentJobInfo.append(currentParentJobInfo)
        allJobInfo[count]=currentJobInfo
    if jobIndex is not None:
      jobSelected = True
      allJobInfo[int(jobIndex)]='selected'
    return (allJobInfo, jobSelected, parentJobInfo)

def getConfigurationsFromDB(_id, stepName=None):
    client = MongoClient(settings.mongo)
    lightsheetDB = client.lightsheet
    if _id=="templateConfigurations":
        jobSteps = list(lightsheetDB.templateConfigurations.find({}, {'_id':0,'steps':1}))
    else:
        jobSteps = list(lightsheetDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'steps':1}))
    if jobSteps:
        jobStepsList = jobSteps[0]["steps"]
        if stepName is not None:
            stepDictionary = next((dictionary for dictionary in jobStepsList if dictionary["stepName"] == stepName), None) 
            if stepDictionary is not None:
                return stepDictionary["parameters"]
            else:
                return 404
        else:
            return jobSteps
    else:
        return 404

def updateDBStates(allJobInfo):
  for currentJobIndex, currentJobInfo in enumerate(allJobInfo):
    if currentJobInfo["state"] not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
      parentJobInformation = requests.get(settings.devOrProductionJACS+'/services/',
                                          params={'service-id':  currentJobInfo["jacs_id"]},
                                          headers=getHeaders(True)).json()
      parentJobInformation = parentJobInformation["resultList"][0]
      if parentJobInformation:
        currentJobInfo["state"]=parentJobInformation["state"]
      childJobStates = requests.get(settings.devOrProductionJACS+'/services/',
                                    params={'parent-id': currentJobInfo["jacs_id"]},
                                    headers=getHeaders(True)).json()
      childJobStates = childJobStates["resultList"]
      print(childJobStates)
      if childJobStates:
        for index,currentStep in enumerate(currentJobInfo["steps"]):
          currentStep["state"] = next(step["state"] for step in childJobStates if step["args"][1] == currentStep["name"])
          currentJobInfo["steps"][index]=currentStep
        allJobInfo[currentJobIndex]=currentJobInfo
  return allJobInfo

def updateDBStatesAndTimes(lightsheetDB):
  allJobInfo = list(lightsheetDB.jobs.find())
  for currentJobIndex, currentJobInfoFromDB in enumerate(allJobInfo):
    if currentJobInfoFromDB["state"] not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
      parentJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                                  params={'service-id':  currentJobInfoFromDB["jacs_id"]},
                                                  headers=getHeaders(True)).json()
      if parentJobInfoFromJACS:
        parentJobInfoFromJACS = parentJobInfoFromJACS["resultList"][0]
        lightsheetDB.jobs.update_one({"_id":currentJobInfoFromDB["_id"]},
                                     {"$set": {"state":parentJobInfoFromJACS["state"] }})
        childJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                            params={'parent-id': currentJobInfoFromDB["jacs_id"]},
                                            headers=getHeaders(True)).json()
        childJobInfoFromJACS = childJobInfoFromJACS["resultList"]
        if childJobInfoFromJACS:
          for index,currentStepFromDB in enumerate(currentJobInfoFromDB["steps"]):
            if currentStepFromDB["state"] not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']: #need to update step
              currentStepFromJACS = next(step for step in childJobInfoFromJACS if step["args"][1] == currentStepFromDB["name"])
              creationTime = convertJACStime(currentStepFromJACS["processStartTime"])
              lightsheetDB.jobs.update_one({"_id":currentJobInfoFromDB["_id"],"steps.name": currentStepFromDB["name"]},
                                           {"$set": {"steps.$.state":currentStepFromJACS["state"],
                                                     "steps.$.creationTime": str(creationTime),
                                                     "steps.$.elapsedTime":str(datetime.now(eastern)-creationTime),
                                                   }})
              if currentStepFromJACS["state"] in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
                endTime = convertJACStime(currentStepFromJACS["modificationDate"])
                lightsheetDB.jobs.update_one({"_id":currentJobInfoFromDB["_id"],"steps.name": currentStepFromDB["name"]},
                                             {"$set": {"steps.$.endTime": str(endTime),
                                                       "steps.$.elapsedTime": str(endTime-creationTime)
                                                     }})
  
def convertJACStime(t):
   t=datetime.strptime(t[:-9], '%Y-%m-%dT%H:%M:%S')
   t=UTC.localize(t).astimezone(eastern)
   return t

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
    return datetime.fromtimestamp(int(v)/1000, eastern)

def insertImage(camera, channel, plane):
    imagePath = path + 'SPC' + specimenString + '_TM' + timepointString + '_ANG000_CM' + camera + '_CHN' + channel.zfill(2) + '_PH0_PLN' + str(plane).zfill(4) + '.tif'
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
  #fig, ax = plt.subplots(nrows = numberOfChannels, ncols = 2*numberOfCameras)#, figsize=(16,8))
  fig = plt.figure();
  fig.set_size_inches(16,8)
  outer = gridspec.GridSpec(numberOfChannels, numberOfCameras, wspace = 0.3, hspace = 0.3)

  for channelCounter, channel in enumerate(channels):
      for cameraCounter, camera in enumerate(cameras):
          inner = gridspec.GridSpecFromSubplotSpec(1,2, subplot_spec = outer[cameraCounter, channelCounter], wspace=0.1, hspace=0.1)
          newList = [(camera, channel, 0)]
          numberOfPlanes = len(glob.glob1(path, '*CM'+camera+'_CHN'+channel.zfill(2)+'*'))
          for plane in range(1,numberOfPlanes):
              newList.append((camera, channel, plane))

          images = pool.starmap(insertImage,newList)
          images = numpy.asarray(images).transpose(1,2,0)
          xy = numpy.amax(images,axis=2)
          xz = numpy.amax(images,axis=1)
          ax1 = plt.Subplot(fig, inner[0])
          ax1.imshow(xy, cmap='gray')
          fig.add_subplot(ax1)
          ax1.axis('auto')
          ax2 = plt.Subplot(fig, inner[1])
          ax2.imshow(xz, cmap='gray')
          fig.add_subplot(ax2)
          ax2.axis('auto')
          ax2.get_yaxis().set_visible(False)
          #ax1.get_shared_y_axes().join(ax1, ax2)
          baseString = 'CM' + camera + '_CHN' + channel.zfill(2)
          ax1.set_title(baseString + ' xy')#, fontsize=12)
          ax2.set_title(baseString + ' xz')#, fontsize=12)

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

def parseJsonData(data):
  keys = data.keys()
  pFrequent = {}
  pSometimes = {}
  pRare = {}
  for key in keys:
    if type(data[key]) is str or type(data[key]) is int:
      # Look up parameter type
      p = Parameter.objects.filter(name=key).first()
      if p is not None:
        if p.frequency == 'F':
          pFrequent[key] = data[key]
        elif p.frequency == 'S':
          pSometimes[key] = data[key]
        elif p.frequency == 'R':
          pRare[key] = data[key]
  forms = {}
  forms['frequent'] = StepForm(pFrequent)
  forms['sometimes'] = StepForm(pSometimes)
  forms['rare'] = StepForm(pRare)
  return forms

def getAppVersion(path):
  mpath = path.split('/')
  result = '/'.join(mpath[0:(len(mpath)-1)]) + '/package.json'
  with open(result) as package_data:
    data = json.load(package_data)
    package_data.close()
    return data['version']
