import numpy, datetime, glob, scipy, re, json, requests, os, ipdb, re, math, operator
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mongoengine import ValidationError, NotUniqueError
from wtforms import *
from multiprocessing import Pool
from scipy import misc
from datetime import datetime
from pytz import timezone
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from app.models import AppConfig, Step, Parameter, Template
from app.settings import Settings


settings = Settings()

# collect the information about existing job used by the job_status page
def getJobInfoFromDB(lightsheetDB, _id=None, parentOrChild="parent", getParameters=False):
  if _id:
    _id = ObjectId(_id)

  if parentOrChild=="parent":
    parentJobInfo = list(lightsheetDB.jobs.find({},{"configAddress":1,"state":1, "jobName":1, "creationDate":1, "jacs_id":1, "lightsheetCommit":1,"steps.name":1,"steps.state":1}))
    for currentJobInfo in parentJobInfo:
      selectedStepNames=''
      for step in currentJobInfo["steps"]:
        selectedStepNames = selectedStepNames+step["name"]+','
      selectedStepNames = selectedStepNames[:-1]
      currentJobInfo.update({'selectedStepNames':selectedStepNames})
      currentJobInfo.update({"selected":""})
      if _id:
        if currentJobInfo["_id"]==_id:
            currentJobInfo.update({"selected":"selected"})
    return parentJobInfo
  elif parentOrChild=="child" and _id:
    if getParameters:
      return list(lightsheetDB.jobs.find({"_id":_id}))
    else:
      return list(lightsheetDB.jobs.find({"_id":_id},{"steps.name":1, "steps.state":1, "steps.creationTime":1, "steps.endTime":1, "steps.elapsedTime":1, "steps.logAndErrorPath":1, "steps.parameters.pause":1}))
  else:
    return 404

# build result object of existing job information
def mapJobsToDict(x):
  result = {}
  if '_id' in x:
    result['id'] = str(x['_id']) if str(x['_id']) is not None else ''
  if 'jobName' in x:
    result['jobName'] = x['jobName'] if x['jobName'] is not None else ''
  if 'creationDate' in x:
    result['creationDate'] = x['creationDate'] if x['creationDate'] is not None else ''
  if 'state' in x:
    result['state'] = x['state'] if x['state'] is not None else ''
  if 'jacs_id' in x:
    result['jacs_id'] = x['jacs_id'] if x['jacs_id'] is not None else ''
  result['selectedSteps']={'names':'','states':''};
  for i,step in enumerate(x["steps"]):
    result['selectedSteps']['names'] = result['selectedSteps']['names'] + step["name"] + ','
    result['selectedSteps']['states'] = result['selectedSteps']['states'] + step["state"] + ','
    if step['state'] not in ["SUCCESSFUL", "RUNNING", "NOT YET QUEUED"]:
      result['selectedSteps']['names'] = result['selectedSteps']['names'] + 'RESET' + ','
      result['selectedSteps']['states'] = result['selectedSteps']['states'] + 'RESET' + ','
    elif "pause" in step['parameters'] and step['parameters']['pause'] and step['state']=="SUCCESSFUL":
      result['selectedSteps']['names'] = result['selectedSteps']['names'] + 'RESUME,RESET' + ','
      result['selectedSteps']['states'] = result['selectedSteps']['states'] + 'RESUME,RESET' + ','

  result['selectedSteps']['names'] = result['selectedSteps']['names'][:-1]
  result['selectedSteps']['states'] = result['selectedSteps']['states'][:-1]
  return result;

# get job information used by jquery datatable
def allJobsInJSON(lightsheetDB):
  parentJobInfo = lightsheetDB.jobs.find({})
  return list(map(mapJobsToDict, parentJobInfo))

# build object with meta information about parameters from the admin interface
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
      elif param.number4 == None:
        param.count = '3'
      else:
        param.count = '4'
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

# build object with information about steps and parameters about admin interface
def buildConfigObject(template_name = None):
  try:
    if not template_name:
      template_name = 'LightSheet'

    sorted_steps = None
    template = Template.objects.filter(name=template_name).first()
    if template:
      steps = template.steps
      sorted_steps = sorted(steps, key=operator.attrgetter('order'))
    templates = Template.objects.all().order_by('order')
    p = Parameter.objects.all()
    paramDict = getParameters(p)
    config = {'steps': sorted_steps, 'parameterDictionary': paramDict, 'templates': templates}
  except ServerSelectionTimeoutError:
    return 404
  return config

# Header for post request
def getHeaders(forQuery=False):
  if forQuery:
    return {'content-type': 'application/json', 'USERNAME': settings.username}
  else:
    return {'content-type': 'application/json', 'USERNAME': settings.username, 'RUNASUSER': 'lightsheet'}

# Timezone for timings
eastern = timezone('US/Eastern')
UTC = timezone('UTC')


# get step information about existing jobs from db
def getJobStepData(_id, mongoClient):
  result = getConfigurationsFromDB(_id, mongoClient, stepName=None)
  if result != None and result != 404 and len(result) > 0 and 'steps' in result[0]:
    return result[0]['steps']
  return None

# get the job parameter information from db
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

# get the job parameter information from db
def getConfigurationsFromDB(lightsheetDB_id, client, globalParameter=None, stepName=None, stepParameter=None):
  lightsheetDB = client.lightsheet
  output={}
  if globalParameter:
    globalParameterValue = list(lightsheetDB.jobs.find({'_id':ObjectId(lightsheetDB_id)},{'_id':0,globalParameter:1}))
    output=globalParameterValue[0]
    if not output:
      output={globalParameter:""}
  else:
    if stepName:
        if stepName=="getArgumentsToRunJob":
          output=getArgumentsToRunJob(lightsheetDB,lightsheetDB_id)
        elif stepName=="all":
          if stepParameter=="name":
            currentJACSJobStepNames = list(lightsheetDB.jobs.find({'_id':ObjectId(lightsheetDB_id)},{'_id':0,"steps.name":1}))
            output={"currentJACSJobStepNames":""}
            for step in currentJACSJobStepNames[0]["steps"]:
              output["currentJACSJobStepNames"] = output["currentJACSJobStepNames"]+step["name"]+','
            output["currentJACSJobStepNames"]=output["currentJACSJobStepNames"][:-1]
          elif stepParameter=="timePoints":
            currentJACSJobTimePoints = list(lightsheetDB.jobs.find({'_id':ObjectId(lightsheetDB_id)},{'_id':0,"steps.parameters.timepoints":1}))
            output={"currentJACSJobTimePoints":""}
            for step in currentJACSJobTimePoints[0]["steps"]:
              timepoints = step["parameters"]["timepoints"];
              timepointStart = timepoints["start"]
              timepointEvery = timepoints["every"]
              timepointEnd = timepoints["end"]
              output["currentJACSJobTimePoints"] = output["currentJACSJobTimePoints"] +str(int(1+math.ceil(timepointEnd-timepointStart)/timepointEvery))+',' 
            output["currentJACSJobTimePoints"]=output["currentJACSJobTimePoints"][:-1]
        else:
         output = list(lightsheetDB.jobs.find({'_id':ObjectId(lightsheetDB_id),'steps.name':stepName},{'_id':0,"steps.$.parameters":1}))
         if output:
          output=output[0]["steps"][0]["parameters"]
    else:
      output = list(lightsheetDB.jobs.find({'_id':ObjectId(lightsheetDB_id)},{'_id':0,'steps':1}))
  if output:
    return output
  else:
    return 404

# get the job parameter information from db
def getArgumentsToRunJob(lightsheetDB, _id):
  lightsheetSteps=["clusterPT","clusterMF","localAP","clusterTF","localEC","clusterCS","clusterFR"]
  currentJobSteps = lightsheetDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'steps.name':1,'steps.parameters.timepoints':1,'steps.parameters.pause':1})
  temp = list(lightsheetDB.jobs.find({"_id":ObjectId(_id)},{'_id':0,"remainingStepNames":1}))
  remainingStepNames=temp[0]["remainingStepNames"];
  output={"currentJACSJobStepNames":'', "currentJACSJobTimePoints":'','configOutputPath':''}
  pauseState=False
  currentStepIndex=0
  while pauseState==False and currentStepIndex<len(currentJobSteps[0]["steps"]):
    if currentJobSteps[0]["steps"][currentStepIndex]["name"] in remainingStepNames:
      step = currentJobSteps[0]["steps"][currentStepIndex]
      output["currentJACSJobStepNames"] = output["currentJACSJobStepNames"]+step["name"]+','
      if step["name"] in lightsheetSteps:
        timepoints = step["parameters"]["timepoints"];
        timepointStart = timepoints["start"]
        timepointEvery = timepoints["every"]
        timepointEnd = timepoints["end"]
        output["currentJACSJobTimePoints"] = output["currentJACSJobTimePoints"] +str(int(1+math.ceil(timepointEnd-timepointStart)/timepointEvery))+','
      if ("pause" in step["parameters"]) :
        pauseState = step["parameters"]["pause"]; 
    currentStepIndex=currentStepIndex+1
  if output["currentJACSJobStepNames"]:
    output["currentJACSJobStepNames"]=output["currentJACSJobStepNames"][:-1]
    output["currentJACSJobTimePoints"]= output["currentJACSJobTimePoints"][:-1]
    configOutputPath = lightsheetDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'configOutputPath':1})
    if configOutputPath[0]:
      output["configOutputPath"]=configOutputPath[0];
    return output
  else:
    return 404

# get latest status information about jobs from db
def updateDBStatesAndTimes(lightsheetDB):
  allJobInfoFromDB = list(lightsheetDB.jobs.find())
  for parentJobInfoFromDB in allJobInfoFromDB:
    if 'jacs_id' in parentJobInfoFromDB: # TODO handle case, when jacs_id is missing
      if parentJobInfoFromDB["state"]: # not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
        if isinstance(parentJobInfoFromDB["jacs_id"],list):
          jacs_ids=parentJobInfoFromDB["jacs_id"]
        else:
          jacs_ids = [parentJobInfoFromDB["jacs_id"]]

        for jacs_id in jacs_ids:
          parentJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                                      params={'service-id':  jacs_id},
                                                      headers=getHeaders(True)).json()
          if parentJobInfoFromJACS and len(parentJobInfoFromJACS["resultList"]) > 0:
            parentJobInfoFromJACS = parentJobInfoFromJACS["resultList"][0]
            lightsheetDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"]},
                                         {"$set": {"state":parentJobInfoFromJACS["state"] }})
            allChildJobInfoFromJACS = requests.get(settings.devOrProductionJACS+'/services/',
                                                params={'parent-id': jacs_id},
                                                headers=getHeaders(True)).json()
            allChildJobInfoFromJACS = allChildJobInfoFromJACS["resultList"]
            if allChildJobInfoFromJACS:
              for currentChildJobInfoFromDB in parentJobInfoFromDB["steps"]:
                if "state" in currentChildJobInfoFromDB and currentChildJobInfoFromDB["state"]: #not in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']: #need to update step
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


def createDBentries(content):
  message = []
  success = False
  if type(content) is list:
    content = content[0]
  keys = content.keys()
  for key in keys:
    obj = content[key]
    if key == 'template':
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
    elif key == 'parameter':
      for o in obj:
        p = Parameter(**o)
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
        if 'parameter' in o:
          # Query for steps and associate them with template
          for param in o['parameter']:
            pObj = Parameter.objects.filter(name=param).first()
            if pObj:
              s['parameter'].append(pObj)
        try:
          s.save()
        except ValidationError as e:
          message.append('Error creating the parameter: ' + str(e))
          pass
        except NotUniqueError as e:
          message.append('Step with the name "{0}" has already been added.'.format(o['name']))
          pass

  if len(message) == 0:
    success = True
    message.append('File has been uploaded successfully.')

  result = {}
  result['message'] = message
  result['success'] = success
  return result

def submitToJACS(lightsheetDB, job_id, continueOrReparameterize):
  job_id=ObjectId(job_id)
  configAddress = settings.serverInfo['fullAddress'] + "/config/" + str(job_id)
  postBody = { "processingLocation": "LSF_JAVA",
               "args": ["-configAddress", configAddress],
               "resources": {"gridAccountId": "lightsheet"}
           }
  try:
    postUrl = settings.devOrProductionJACS + '/async-services/genericServicePipeline' #'/async-services/lightsheetPipeline'
    requestOutput = requests.post(postUrl,
                                  headers=getHeaders(),
                                  data=json.dumps(postBody))
    requestOutputJsonified = requestOutput.json()
    creationDate = job_id.generation_time
    creationDate = str(creationDate.replace(tzinfo=UTC).astimezone(eastern))
    if continueOrReparameterize:
        lightsheetDB.jobs.update_one({"_id": job_id},{"$push": {"jacsStatusAddress": 'http://jacs-dev.int.janelia.org:8080/job/'+requestOutputJsonified["_id"], "jacs_id": requestOutputJsonified["_id"] }})
    else:
        lightsheetDB.jobs.update_one({"_id":job_id},{"$set": {"jacs_id":[requestOutputJsonified["_id"]], "configAddress":configAddress, "creationDate":creationDate[:-6]}})

    #JACS service states
    # if any are not Canceled, timeout, error, or successful then
    #updateLightsheetDatabaseStatus
    updateDBStatesAndTimes(lightsheetDB)
    submissionStatus = "success"
  except requests.exceptions.RequestException as e:
    print('Exception occured')
    submissionStatus = e
    if not continueOrReparameterize:
      lightsheetDB.jobs.remove({"_id":job_id})
