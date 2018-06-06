# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb
from flask import render_template, request, jsonify, abort
from pymongo import MongoClient
from collections import OrderedDict
from datetime import datetime
from app import app
from app.settings import Settings
from bson.objectid import ObjectId
from app.utils import *
from app.jobs_io import reformatDataToPost, parseJsonDataNoForms
from app.models import Dependency
from bson.objectid import ObjectId

settings = Settings()

# Prefix for all default pipeline step json file names
defaultFileBase = None
if hasattr(settings, 'defaultFileBase'):
  defaultFileBase = settings.defaultFileBase

# Location to store json files
outputDirectoryBase = None
if hasattr(settings, 'outputDirectoryBase'):
  outputDirectoryBase = settings.outputDirectoryBase
global_error = None

# Mongo client
mongosettings = 'mongodb://' + app.config['MONGODB_SETTINGS']['host'] + ':' + str(app.config['MONGODB_SETTINGS']['port']) + '/'
client = MongoClient(mongosettings)
# lightsheetDB is the database containing lightsheet job information and parameters
lightsheetDB = client.lightsheet

@app.route('/', methods=['GET','POST'])
def index():
  submissionStatus = None
  lightsheetDB_id = request.args.get('lightsheetDB_id')
  reparameterize = request.args.get('reparameterize');
  config = buildConfigObject()
  if lightsheetDB_id == 'favicon.ico':
    lightsheetDB_id = None
  pipelineSteps = {}
  formData = None
  countJobs = 0
  jobData =  getJobStepData(lightsheetDB_id, client) # get the data for all jobs
  ableToReparameterize=True
  if jobData:
    if (jobData[-1]["parameters"]["pause"]==0 and jobData[-1]["state"]=="SUCCESSFUL") or any( (step["state"] in "RUNNING CREATED") for step in jobData):
      ableToReparameterize=False

  if reparameterize=="true" and lightsheetDB_id:
    reparameterize=True
    remainingStepNames = lightsheetDB.jobs.find({"_id":ObjectId(lightsheetDB_id)},{"remainingStepNames":1})
    if not ableToReparameterize:
      abort(404)
  else:
    reparameterize=False

  # match data on step name
  matchNameIndex = {}
  if type(jobData) is list:
    if lightsheetDB_id != None:
      for i in range(len(jobData)):
        if 'name' in jobData[i]:
          matchNameIndex[jobData[i]['name']] = i
      # go through all steps and find those, which are used by the current job
      for step in config['steps']:
        currentStep = step.name
        # If loading previous run parameters for specific step, then it should be checked sett editable
        if currentStep in matchNameIndex.keys():
          stepData = jobData[matchNameIndex[currentStep]]
          editState = 'enabled'
          checkboxState = 'checked'
          if reparameterize and stepName not in remainingStepNames:
            editState = 'disabled'
            checkboxState = 'unchecked'
          countJobs += 1
          forms = None
          jobs = parseJsonDataNoForms(stepData, currentStep, config)
          # Pipeline steps is passed to index.html for formatting the html based
          pipelineSteps[currentStep] = {
            'stepName': step.name,
            'stepDescription': step.description,
            'inputJson': None,
            'state': editState,
            'checkboxState': checkboxState,
            'forms': forms,
            'jobs': jobs
          }
  elif type(jobData) is dict:
    submissionStatus = 'Job cannot be loaded.'
  if request.method == 'POST':
    #If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
    #lightsheetDB is the database containing lightsheet job information and parameters
    if request.json != '[]' and request.json != None:
      file = open(settings.gitVersionIdPath,'r')
      currentLightsheetCommit = file.readline()
      file.close()
      # trim ending \n
      if currentLightsheetCommit.endswith('\n'):
        currentLightsheetCommit = currentLightsheetCommit[:-1]
      userDefinedJobName=[]

      # get the name of the job first
      jobName = request.json['jobName']
      del(request.json['jobName'])

      # delete the jobName entry from the dictionary so that the other entries are all steps
      jobSteps = list(request.json.keys())
#      stepsString = ','.join(str(y) for y in jobSteps)
#      allSelectedTimePoints= ', '.join(timePointList)
      # go through the data and prepare it for posting it to db
      processedDataTemp = reformatDataToPost(request.json)
      processedData=[]
      remainingStepNames=[];
      allStepNames=["clusterPT","clusterMF","localAP","clusterTF","localEC","clusterCS", "clusterFR"]
      for stepName in allStepNames:
        currentStepDictionary = next((dictionary for dictionary in processedDataTemp if dictionary["name"] == stepName), None) 
        if currentStepDictionary:
            remainingStepNames.append(currentStepDictionary["name"])
            processedData.append(currentStepDictionary)

      # Prepare the db data
      dataToPostToDB = {"jobName": jobName,
                        "state": "NOT YET QUEUED",
                        "lightsheetCommit":currentLightsheetCommit,
                        "remainingStepNames":remainingStepNames,
                        "steps": processedData
                       }

      # Insert the data to the db
      if reparameterize:
        lightsheetDB_id=ObjectId(lightsheetDB_id)
        lightsheetDB.jobs.update_one({"_id": lightsheetDB_id},{"$set": dataToPostToDB})
      else:
        lightsheetDB_id = lightsheetDB.jobs.insert_one(dataToPostToDB).inserted_id
      
      submissionStatus = submitToJACS(lightsheetDB, lightsheetDB_id, reparameterize)

  updateDBStatesAndTimes(lightsheetDB)
  parentJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id,"parent")
  jobs = allJobsInJSON(lightsheetDB)
  # if len(pipelineSteps) > 0:
  #Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                       title='Home',
                       pipelineSteps=pipelineSteps,
                       parentJobInfo = parentJobInfo, # used by job status
                       logged_in=True,
                       config = config,
                       version = getAppVersion(app.root_path),
                       lightsheetDB_id = lightsheetDB_id,
                       jobsJson= jobs, # used by the job table
                       submissionStatus = None)


@app.route('/job_status', methods=['GET','POST'])
def job_status():
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    #Mongo client
    updateDBStatesAndTimes(lightsheetDB)
    parentJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id, "parent")
    childJobInfo=[]
    if request.method == 'POST':
      pausedJobInformation=list(lightsheetDB.jobs.find({"_id":ObjectId(lightsheetDB_id)}))
      pausedJobInformation=pausedJobInformation[0]
      pausedStates = [step['parameters']['pause'] for step in pausedJobInformation["steps"]]
      pausedStepIndex = next((i for i, pausable in enumerate(pausedStates) if pausable), None)
      pausedJobInformation["steps"][pausedStepIndex]["parameters"]["pause"] = 0
      print(pausedJobInformation["remainingStepNames"])
      print(pausedJobInformation["steps"][pausedStepIndex]["name"])
      while pausedJobInformation["remainingStepNames"][0]!=pausedJobInformation["steps"][pausedStepIndex]["name"]:
        pausedJobInformation["remainingStepNames"].pop(0)
      pausedJobInformation["remainingStepNames"].pop(0) #Remove steps that have been completed/approved
      print(pausedJobInformation["remainingStepNames"])
      lightsheetDB.jobs.update_one({"_id": ObjectId(lightsheetDB_id)},{"$set": pausedJobInformation})
      submissionStatus = submitToJACS(lightsheetDB, lightsheetDB_id, True)
      updateDBStatesAndTimes(lightsheetDB)
    if lightsheetDB_id is not None:
        childJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id, "child")
        childJobInfo = childJobInfo[0]["steps"]
    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentJobInfo=parentJobInfo,
                           childJobInfo=childJobInfo,
                           logged_in=True,
                           version = getAppVersion(app.root_path))


@app.route('/search')
def search():
    return render_template('search.html',
                           logged_in=True,
                           version = getAppVersion(app.root_path))


@app.route('/register', methods=['GET', 'POST'])
def register():
  form = RegistrationForm(request.form)
  if request.method == 'POST' and form.validate():
    user = User(form.username.data, form.email.data,
                form.password.data)
    db_session.add(user)
    flash('Thanks for registering')
    return redirect(url_for('login'))
  return render_template('register.html',
                         form=form,
                         version=getAppVersion(app.root_path))


@app.route('/login')
def login():
  return render_template('login.html',
                         logged_in=False,
                         version=getAppVersion(app.root_path))


@app.route('/config/<lightsheetDB_id>', methods=['GET'])
def config(lightsheetDB_id):
    globalParameter = request.args.get('globalParameter')
    stepName = request.args.get('stepName')
    stepParameter = request.args.get('stepParameter')
    output=getConfigurationsFromDB(lightsheetDB_id, client, globalParameter, stepName, stepParameter)
    if output==404:
        abort(404)
    else:
        return jsonify(output)

def createDependencyResults(dependencies):
  result = []
  for d in dependencies:
      # need to check here, if simple value transfer (for string or float values) or if it's a nested field
      obj = {}
      obj['input'] = d.inputField.name if d.inputField and d.inputField.name is not None else ''
      obj['output'] =  d.outputField.name if d.outputField and d.outputField.name is not None else ''
      obj['pattern'] = d.pattern if d.pattern is not None else ''
      obj['step'] = d.outputStep.name if d.outputStep is not None else ''
      obj['formatting'] = d.inputField.formatting if d.inputField.formatting is not None else ''
      result.append(obj)
  return result

@app.context_processor
def add_value_dependency_object():
  dep = Dependency.objects.filter(dependency_type='V');
  result = []
  if dep is not None:
    result = createDependencyResults(dep)
  return dict(value_dependency=result)

@app.context_processor
def add_dimension_dependency_object():
  dep = Dependency.objects.filter(dependency_type='D');
  result = []
  if dep is not None:
    result = createDependencyResults(dep)
  return dict(dimension_dependency=result)
