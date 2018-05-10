# Contains routes and functions to pass content to the template layer
import requests, json, os, math, datetime, bson, re, subprocess, ipdb
from flask import render_template, request, jsonify, abort
from pymongo import MongoClient
from collections import OrderedDict
from datetime import datetime
from app import app
from app.settings import Settings
from bson.objectid import ObjectId
from app.utils import *
from app.jobs_io import *

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
  job_id = request.args.get('lightsheetDB_id')
  config = buildConfigObject()
  if job_id == 'favicon.ico':
    job_id = None

  pipelineSteps = {}
  formData = None
  countJobs = 0
  jobData =  getJobStepData(job_id, client) # get the data for all jobs
  # match data on step name
  matchNameIndex = {}
  if type(jobData) is list:
    if job_id != None:
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
    timePointsDefault = "11"
    stepParameters=[]
    file = open(settings.gitVersionIdPath,'r')
    currentLightsheetCommit = file.readline()
    file.close()
    # trim ending \n
    if currentLightsheetCommit.endswith('\n'):
      currentLightsheetCommit = currentLightsheetCommit[:-1]
    userDefinedJobName=[]
    if request.json != '[]' and request.json != None:
      # get the name of the job first
      jobName = request.json['jobName']
      del(request.json['jobName'])

      # delete the jobName entry from the dictionary so that the other entries are all steps
      jobSteps = list(request.json.keys())
      stepsString = ','.join(str(y) for y in jobSteps)
      allSelectedTimePoints= ', '.join(timePointsDefault for y in jobSteps)
      # go through the data and prepare it for posting it to db
      processedData = reformatDataToPost(request.json)
      # Prepare the db data
      dataToPostToDB = {"jobName": jobName,
                        "state": "NOT YET QUEUED",
                        "lightsheetCommit":currentLightsheetCommit,
                        "selectedStepNames": stepsString,
                        "selectedTimePoints": allSelectedTimePoints,
                        "steps": processedData
                       }

      # Insert the data to the db
      newId = lightsheetDB.jobs.insert_one(dataToPostToDB).inserted_id
      configAddress = settings.serverInfo['fullAddress'] + "/config/" + str(newId)
      postBody = { "processingLocation": "LSF_JAVA",
                   "args": ["-configAddress", configAddress,
                            "-allSelectedStepNames", stepsString,
                            "-allSelectedTimePoints", allSelectedTimePoints],
                   "resources": {"gridAccountId": "lightsheet"}
               }
      try:
        postUrl = settings.devOrProductionJACS + '/async-services/lightsheetProcessing'
        requestOutput = requests.post(postUrl,
                                      headers=getHeaders(),
                                      data=json.dumps(postBody))
        requestOutputJsonified = requestOutput.json()
        creationDate = newId.generation_time
        creationDate = str(creationDate.replace(tzinfo=UTC).astimezone(eastern))
        lightsheetDB.jobs.update_one({"_id":newId},{"$set": {"jacs_id":requestOutputJsonified["_id"], "configAddress":configAddress, "creationDate":creationDate[:-6]}})

        #JACS service states
        # if any are not Canceled, timeout, error, or successful then
        #updateLightsheetDatabaseStatus
        updateDBStatesAndTimes(lightsheetDB)
        submissionStatus = "success"
      except requests.exceptions.RequestException as e:
        pprint('Exception occured')
        submissionStatus = e
        lightsheetDB.jobs.remove({"_id":newId})

  updateDBStatesAndTimes(lightsheetDB)
  parentJobInfo = getJobInfoFromDB(lightsheetDB, job_id,"parent")
  jobs = allJobsInJSON(lightsheetDB)
  # if len(pipelineSteps) > 0:
  #   ipdb.set_trace()
  #Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                       title='Home',
                       pipelineSteps=pipelineSteps,
                       parentJobInfo = parentJobInfo, # used by job status
                       logged_in=True,
                       config = config,
                       version = getAppVersion(app.root_path),
                       lightsheetDB_id = job_id,
                       jobsJson= jobs, # used by the job table
                       submissionStatus = submissionStatus)


@app.route('/job_status', methods=['GET'])
def job_status():
    before=datetime.now()

    lightsheetDB_id = request.args.get('lightsheetDB_id')
    #Mongo client
    updateDBStatesAndTimes(lightsheetDB)
    parentJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id, "parent")
    childJobInfo=[]
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
    stepName = request.args.get('stepName')
    output=getConfigurationsFromDB(lightsheetDB_id, client, stepName)
    if output==404:
        abort(404)
    else:
        return jsonify(output)