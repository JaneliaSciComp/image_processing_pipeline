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
from app.models import AppConfig, Step, Parameter, Template, PipelineInstance
from app.settings import Settings


settings = Settings()

# collect the information about existing job used by the job_status page
def getJobInfoFromDB(imageProcessingDB, _id=None, parentOrChild="parent"):
  allSteps=Step.objects.all()
  if _id:
    _id = ObjectId(_id)

  if parentOrChild=="parent":
    parentJobInfo = list(imageProcessingDB.jobs.find({},{"configAddress":1,"state":1, "jobName":1, "creationDate":1, "jacs_id":1, "steps.name":1,"steps.state":1}))
    for currentJobInfo in parentJobInfo:
      selectedStepNames=''
      for step in currentJobInfo["steps"]:
        stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]), None)
        if stepTemplate == None or stepTemplate.submit: #None implies a deprecated name
          selectedStepNames = selectedStepNames+step["name"]+','
      selectedStepNames = selectedStepNames[:-1]
      currentJobInfo.update({'selectedStepNames':selectedStepNames})
      currentJobInfo.update({"selected":""})
      if _id:
        if currentJobInfo["_id"]==_id:
            currentJobInfo.update({"selected":"selected"})
    return parentJobInfo
  elif parentOrChild=="child" and _id:
      childJobInfo=[]
      tempList  = list(imageProcessingDB.jobs.find({"_id":_id},{"steps.name":1, "steps.state":1, "steps.creationTime":1, "steps.endTime":1, "steps.elapsedTime":1, "steps.logAndErrorPath":1, "steps.parameters.pause":1}))
      tempList = tempList[0];
      for step in tempList["steps"]:
        stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]), None)
        if stepTemplate == None or stepTemplate.submit: #None implies a deprecated name
          childJobInfo.append(step)
      return childJobInfo
  else:
    return 404

# build result object of existing job information
def mapJobsToDict(x):
  allSteps=Step.objects.all()
  result = {}
  if '_id' in x:
    result['id'] = str(x['_id']) if str(x['_id']) is not None else ''
  if 'jobName' in x:
    result['jobName'] = x['jobName'] if x['jobName'] is not None else ''
  if 'submissionAddress' in x:
    result['submissionAddress'] = x['submissionAddress'] if x['submissionAddress'] is not None else ''
  else: result['submissionAddress'] = ''
  if 'creationDate' in x:
    result['creationDate'] = x['creationDate'] if x['creationDate'] is not None else ''
  if 'state' in x:
    result['state'] = x['state'] if x['state'] is not None else ''
  if 'jacs_id' in x:
    result['jacs_id'] = x['jacs_id'] if x['jacs_id'] is not None else ''
  result['selectedSteps']={'names':'','states':'','submissionAddress':''};
  for i,step in enumerate(x["steps"]):
    stepTemplate = next((stepTemplate for stepTemplate in allSteps if stepTemplate.name == step["name"]), None)
    if stepTemplate == None or stepTemplate.submit: #None implies a deprecated name
      result['selectedSteps']['submissionAddress'] = result['submissionAddress']
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
def allJobsInJSON(imageProcessingDB):
  parentJobInfo = imageProcessingDB.jobs.find({},{"_id":1,"jobName":1,"submissionAddress":1, "creationDate":1, "state":1, "jacs_id":1,"steps.state":1,"steps.name":1,"steps.parameters.pause":1})
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
def buildConfigObject():
  try:
    sorted_steps = {}
    templates = Template.objects.all()
    allSteps = Step.objects.all().order_by('order')
    for template in templates:
      steps = template.steps
      sorted_steps[template.name] = sorted(steps, key=operator.attrgetter('order'))

    templates = Template.objects.all().order_by('order')
    p = Parameter.objects.all()
    paramDict = getParameters(p)
    config = {'steps': sorted_steps, 'stepsAll': allSteps, 'parameterDictionary': paramDict, 'templates': templates}
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
def getConfigurationsFromDB(imageProcessingDB_id, client, globalParameter=None, stepName=None, stepParameter=None):
  imageProcessingDB = client.lightsheet
  output={}
  if globalParameter:
    globalParameterValue = list(imageProcessingDB.jobs.find({'_id':ObjectId(imageProcessingDB_id)},{'_id':0,globalParameter:1}))
    output=globalParameterValue[0]
    if not output:
      output={globalParameter:""}
  else:
    if stepName:
        if stepName=="getArgumentsToRunJob":
          output=getArgumentsToRunJob(imageProcessingDB,imageProcessingDB_id)
        else:
         output = list(imageProcessingDB.jobs.find({'_id':ObjectId(imageProcessingDB_id),'steps.name':stepName},{'_id':0,"steps.$.parameters":1}))
         if output:
          output=output[0]["steps"][0]["parameters"]
    else:
      output = list(imageProcessingDB.jobs.find({'_id':ObjectId(imageProcessingDB_id)},{'_id':0,'steps':1}))

  if output:
    return output
  return 404

# get the job parameter information from db
def getArgumentsToRunJob(imageProcessingDB, _id):
  currentJobSteps = imageProcessingDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'steps.name':1,'steps.parameters.pause':1})
  temp = list(imageProcessingDB.jobs.find({"_id":ObjectId(_id)},{'_id':0,"remainingStepNames":1}))
  if "remainingStepNames" in temp[0]:
    remainingStepNames=temp[0]["remainingStepNames"]
  else:
    remainingStepNames=[]
    for step in currentJobSteps[0]["steps"]:
      remainingStepNames.append(step["name"])

  output={"currentJACSJobStepNames":'','configOutputPath':''}
  pauseState=False
  currentStepIndex=0
  while pauseState==False and currentStepIndex<len(currentJobSteps[0]["steps"]):
    if currentJobSteps[0]["steps"][currentStepIndex]["name"] in remainingStepNames:
      step = currentJobSteps[0]["steps"][currentStepIndex]
      output["currentJACSJobStepNames"] = output["currentJACSJobStepNames"]+step["name"]+','
      if ("pause" in step["parameters"]) :
        pauseState = step["parameters"]["pause"]; 
    currentStepIndex=currentStepIndex+1
  if output["currentJACSJobStepNames"]:
    output["currentJACSJobStepNames"]=output["currentJACSJobStepNames"][:-1]
    configOutputPath = imageProcessingDB.jobs.find({'_id':ObjectId(_id)},{'_id':0,'configOutputPath':1})
    if configOutputPath[0]:
      output["configOutputPath"]=configOutputPath[0];
  if currentJobSteps:
    return output
  else:
    return 404

# get latest status information about jobs from db
def updateDBStatesAndTimes(imageProcessingDB):
  allJobInfoFromDB = list(imageProcessingDB.jobs.find())
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
            imageProcessingDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"]},
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

                    imageProcessingDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"],"steps.name": currentChildJobInfoFromDB["name"]},
                                                 {"$set": {"steps.$.state":currentChildJobInfoFromJACS["state"],
                                                           "steps.$.creationTime": creationTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                           "steps.$.elapsedTime":str(datetime.now(eastern)-creationTime),
                                                           "steps.$.logAndErrorPath":outputPath
                                                         }})

                    if currentChildJobInfoFromJACS["state"] in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:
                      endTime = convertJACStime(currentChildJobInfoFromJACS["modificationDate"])
                      imageProcessingDB.jobs.update_one({"_id":parentJobInfoFromDB["_id"],"steps.name": currentChildJobInfoFromDB["name"]},
                                                   {"$set": {"steps.$.endTime": endTime.strftime("%Y-%m-%d %H:%M:%S"),
                                                             "steps.$.elapsedTime": str(endTime-creationTime)
                                                           }})
  
def convertJACStime(t):
   t=datetime.strptime(t[:-9], '%Y-%m-%dT%H:%M:%S')
   t=UTC.localize(t).astimezone(eastern)
   return t


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

def createConfig(content):
  pInstance = PipelineInstance()
  pInstance.content = json.dumps(content)
  pInstance.save()

  message = []
  result = {}
  # Create new database objects configuration and configuration instances
  result['message'] = message
  result['success'] = True
  result['name'] = pInstance.name
  return result

def submitToJACS(imageProcessingDB, job_id, continueOrReparameterize):
  job_id=ObjectId(job_id)
  configAddress = settings.serverInfo['fullAddress'] + "/config/" + str(job_id)
  postBody = { "processingLocation": "LSF_JAVA",
               "args": ["-configAddress", configAddress],
               "resources": {"gridAccountId": "lightsheet"}
           }
  try:
    postUrl = settings.devOrProductionJACS + '/async-services/lightsheetPipeline'
    requestOutput = requests.post(postUrl,
                                  headers=getHeaders(),
                                  data=json.dumps(postBody))
    requestOutputJsonified = requestOutput.json()
    creationDate = job_id.generation_time
    creationDate = str(creationDate.replace(tzinfo=UTC).astimezone(eastern))
    if continueOrReparameterize:
        imageProcessingDB.jobs.update_one({"_id": job_id},{"$push": {"jacsStatusAddress": 'http://jacs-dev.int.janelia.org:8080/job/'+requestOutputJsonified["_id"], "jacs_id": requestOutputJsonified["_id"] }})
    else:
        imageProcessingDB.jobs.update_one({"_id":job_id},{"$set": {"jacs_id":[requestOutputJsonified["_id"]], "configAddress":configAddress, "creationDate":creationDate[:-6]}})

    #JACS service states
    # if any are not Canceled, timeout, error, or successful then
    #updateLightsheetDatabaseStatus
    updateDBStatesAndTimes(imageProcessingDB)
    submissionStatus = "success"
  except requests.exceptions.RequestException as e:
    print('Exception occured')
    submissionStatus = e
    if not continueOrReparameterize:
      imageProcessingDB.jobs.remove({"_id":job_id})
