import sys, numpy, datetime, glob, scipy, re, json, requests, os, ipdb
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from wtforms import Form, StringField, validators
from mongoengine.queryset.visitor import Q
from pylab import figure, axes, pie, title, show
from multiprocessing import Pool
from pprint import pprint
from scipy import misc
from datetime import datetime
from pytz import timezone
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from app.models import AppConfig, Step, Parameter
from app.forms import StepForm
from app.settings import Settings

settings = Settings()


def testDatabaseStatus(db):
  # Issue the serverStatus command and print the results
  serverStatusResult = db.command("serverStatus")


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
  try:
    steps = Step.objects.all().order_by('order')
    parameter = Parameter.objects.all()
    paramNew = getType(parameter)
    config = {'steps': steps, 'parameter': paramNew}
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


def getConfigurationsFromDB(_id, mongoClient, stepName=None):
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


def customPrint(printObj, message):
  pprint("\n>>>>>>>>>>>>>>>>>>>>>>")
  pprint(message)
  pprint(printObj)
  pprint("<<<<<<<<<<<<<<<<<<<<<<\n")


def getServiceDataFromDB(lightsheetDB):
  serviceData = list(lightsheetDB.jobs.find())
  if (len(serviceData) > 0):
    for count, dictionary in enumerate(serviceData):
      dictionary["selected"] = '';
      dictionary["creationDate"] = str(dictionary["_id"].generation_time)
      dictionary["index"] = str(count)
  return serviceData


def getParentServiceDataFromJACS(lightsheetDB, serviceIndex=None, serviceIndexId=None):
  # Function to get information about parent jobs from JACS database marks currently selected j
  allJACSids = list(lightsheetDB.jobs.find({}, {'_id': 0, 'jacs_id': 1}))
  allJACSids = [str(dictionary['jacs_id']) if 'jacs_id' in dictionary.keys() else "" for dictionary in allJACSids]
  requestOutputJsonified = [requests.get(settings.devOrProductionJACS + '/services/',
                                         params={'service-id': JACSid},
                                         headers=getHeaders(True)).json()
                            for JACSid in allJACSids]
  serviceData = []
  count = 0
  for jobInformation in requestOutputJsonified:
    if jobInformation['resultList'] is not None and len(jobInformation['resultList']) > 0:
      jobInformationResultListDictionary = jobInformation['resultList'][0]
      jobInformationResultListDictionary.update(
        (k, str(convertEpochTime(v))) for k, v in jobInformationResultListDictionary.items() if k == "creationDate")
      jobInformationResultListDictionary["selected"] = ''
      jobInformationResultListDictionary["index"] = str(count)
      serviceData.append(jobInformationResultListDictionary)
      count = count + 1
      # serviceData = [dictionary['resultList'][0] for dictionary in requestOutputJsonified]
  if serviceData and serviceIndex is not None:
    serviceData[int(serviceIndex)]["selected"] = 'selected'

  return serviceData


def getChildServiceDataFromJACS(parentId):
  # Function to get information from JACS service databases
  # Gets information about currently running and already completed jobs
  requestOutput = requests.get(settings.devOrProductionJACS + '/services/',
                               params={'parent-id': str(parentId)},
                               headers=getHeaders(True))
  requestOutputJsonified = requestOutput.json()
  serviceData = requestOutputJsonified['resultList']
  for dictionary in serviceData:  # convert date to nicer string
    dictionary.update(
      (k, convertEpochTime(v)) for k, v in dictionary.items() if (k == "creationDate" or k == "modificationDate"))
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


def parseJsonData(data):
  keys = data.keys()
  pFrequent = {}
  pSometimes = {}
  pRare = {}
  forms = {}
  # For each key, look up the parameter type and add parameter to the right type of form based on that:
  for key in keys:
    param = Parameter.objects.filter(name=key).first()
    if param != None:
      if param.frequency == 'F':
        pFrequent[key] = data[key]
      elif param.frequency == 'S':
        pSometimes[key] = data[key]
      elif param.frequency == 'R':
        pRare[key] = data[key]
  forms['frequent'] = StepForm(pFrequent)
  forms['sometimes'] = StepForm(pSometimes)
  forms['rare'] = StepForm(pRare)
  return forms


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
