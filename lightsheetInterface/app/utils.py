import requests
from mongoengine.queryset.visitor import Q
import sys, numpy, datetime, glob, scipy
from scipy import misc
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from multiprocessing import Pool
from pprint import pprint
from pylab import figure, axes, pie, title, show
from datetime import datetime
from pytz import timezone
import json
import re
from app.models import AppConfig, Step, Parameter
from app.settings import Settings
from wtforms import Form, StringField, validators

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
  # oneParam = Config.objects(Q(number2=None) & Q(number3=None) & (Q(type=None) | Q(type='')))
  # twoParam = Config.objects(Q(number2__ne=None) & Q(number3=None) & Q(type=None))
  # threeParam = Config.objects( Q(number1__ne=None) & Q(number2__ne=None) & Q(number3__ne=None) & (Q(type=None) | Q(type='')) )
  # steps = Config.objects(type='S')
  # config = {'onenum': oneParam, 'twonum': twoParam, 'threenum': threeParam, 'steps': steps}
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

def getServiceDataFromDB(lightsheetDB):
    serviceData = list(lightsheetDB.jobs.find())
    for count, dictionary in enumerate(serviceData):
        dictionary["selected"]='';
        dictionary["creationDate"]=str(dictionary["_id"].generation_time)
        dictionary["index"]=str(count)
    return serviceData

def getParentServiceDataFromJACS(lightsheetDB, serviceIndex=None):
    #Function to get information about parent jobs from JACS database marks currently selected job
    allJACSids = list(lightsheetDB.jobs.find({},{'_id':0, 'jacs_id': 1}))
    allJACSids = [str(dictionary['jacs_id']) for dictionary in allJACSids]
    requestOutputJsonified = [requests.get(settings.devOrProductionJACS+'/services/',
                                           params={'service-id':  JACSid},
                                           headers=getHeaders(True)).json()
                              for JACSid in allJACSids]
    serviceData = None

    for dictionary in requestOutputJsonified:
      print(type(dictionary))
      if dictionary['resultList'] != None and len(dictionary['resultList']) > 0:
        serviceData = dictionary['resultList'][0]
        for count, dictionary in enumerate(serviceData): #convert date to nicer string
          dictionary.update((k,str(convertEpochTime(v))) for k, v in dictionary.items() if k=="creationDate")
          dictionary["selected"]=''
          dictionary["index"] = str(count)

        # serviceData = [dictionary['resultList'][0] for dictionary in requestOutputJsonified]
        if serviceIndex is not None and (serviceIndex!="favicon.ico"):
            serviceData[int(float(serviceIndex))]["selected"] = 'selected'
    return serviceData

def getChildServiceDataFromJACS(parentId):
    #Function to get information from JACS service databases
    #Gets information about currently running and already completed jobs
    requestOutput = requests.get(settings.devOrProductionJACS+'/services/',
                                 params={'parent-id': str(parentId)},
                                 headers=getHeaders(True))
    requestOutputJsonified = requestOutput.json()
    serviceData=requestOutputJsonified['resultList']
    for dictionary in serviceData: #convert date to nicer string
         dictionary.update((k,convertEpochTime(v)) for k, v in dictionary.items() if (k=="creationDate" or k=="modificationDate") )
    serviceData = requestOutputJsonified['resultList']
    serviceData = sorted(serviceData, key=lambda k: k['creationDate'])
    return serviceData

def convertEpochTime(v):
    return datetime.fromtimestamp(int(v)/1000, eastern)


def generateThumbnailImages():
  path = sys.argv[1]
  timepoint = sys.argv[2]
  specimen = sys.argv[3]
  cameras = sys.argv[4].split(',')
  channels = sys.argv[5].split(',')
  specimenString = specimen.zfill(2)
  timepointString = timepoint.zfill(5)
  path = path+'/SPM' + specimenString + '/TM' + timepointString + '/ANG000/'

  def insertImage(camera, channel, plane):
      imagePath = path + 'SPC' + specimenString + '_TM' + timepointString + '_ANG000_CM' + camera + '_CHN' + channel.zfill(2) + '_PH0_PLN' + str(plane).zfill(4) + '.tif'
      return misc.imread(imagePath)

  if __name__ == '__main__':
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

def loadParameters(fileName):
  with open(fileName) as data_file:
    data = json.load(data_file)
    parseJsonData(data)


def parseJsonData(data):
  keys = data.keys()
  regSingleNum = '[\d|,]'
  regNumParameter = '[,*?]'
  parameter = {}

  for key in keys:
    if type(data[key]) is str:
      parameter[key] = data[key]
    elif type(data[key]) is int:
      parameter[key] = data[key]

