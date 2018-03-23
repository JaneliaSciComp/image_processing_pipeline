import requests, json, os, math, datetime, bson, re, subprocess, ipdb
from flask import render_template, request, jsonify, abort
from pymongo import MongoClient
from collections import OrderedDict
from datetime import datetime
from app import app
from app.settings import Settings
from bson.objectid import ObjectId
from app.utils import *

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
client = MongoClient(settings.mongo)
# lightsheetDB is the database containing lightsheet job information and parameters
lightsheetDB = client.lightsheet

app.route('/register', methods=['GET', 'POST'])


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


@app.route('/submit', methods=['GET', 'POST'])
def submit():
  if request.method == 'POST':
    keys = request.form.keys()
    for k in iter(keys):
      print(k)
  return 'form submitted'


@app.route('/', methods=['GET','POST'])
def index():
  # ipdb.set_trace()
  job_id = request.args.get('lightsheetDB_id')
  config = buildConfigObject()
  if job_id == 'favicon.ico':
    job_id = None

  pipelineSteps = {}
  formData = None
  countJobs = 0
  stepData =  getJobStepData(job_id, client)
  # go through all steps and find those, which are used by the current job
  for step in config['steps']:
    currentStep = step.name
    if stepData != None and job_id != None:
      # If loading previous run parameters for specific step, then it should be checked and editable
      for jobStep in stepData:
        if currentStep == jobStep['name']:
          editState = 'enabled'
          checkboxState = 'checked'
          countJobs += 1
          forms = parseJsonData(stepData)
          # Pipeline steps is passed to index.html for formatting the html based
          pipelineSteps[currentStep] = {
            'stepName': step.name,
            'stepDescription': step.description,
            'inputJson': None,
            'state': editState,
            'checkboxState': checkboxState,
            'forms': forms
          }

  if request.method == 'POST':
      #If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
      #lightsheetDB is the database containing lightsheet job information and parameters
      allSelectedStepNames=""
      allSelectedTimePoints=""
      stepParameters=[]
      currentLightsheetCommit = subprocess.check_output(['git', '--git-dir', settings.pipelineGit, 'rev-parse', 'HEAD']).strip().decode("utf-8")
      userDefinedJobName=[]

      postedData = request.get_json()
      if not postedData:
          #Then submission from webpage itself
          pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']
          for currentStep in pipelineOrder:
              text = request.form.get(currentStep) #will be none if checkbox is not checked
              if text is not None:
                  #Store step parameters and step names/times to use as arguments for the post
                  jsonifiedText = json.loads(text, object_pairs_hook=OrderedDict)
                  stepParameters.append({"name":currentStep, "state":"NOT YET QUEUED",
                                         "creationTime":"N/A", "endTime":"N/A",
                                         "elapsedTime":"N/A","logAndErrorPath": "N/A",
                                         "parameters": jsonifiedText})
                  allSelectedStepNames = allSelectedStepNames+currentStep+","
                  numTimePoints = math.ceil(1+(jsonifiedText["timepoints"]["end"] - jsonifiedText["timepoints"]["start"])/jsonifiedText["timepoints"]["every"])
                  allSelectedTimePoints = allSelectedTimePoints+str(numTimePoints)+", "

          if stepParameters:
              #Finish preparing the post body
              allSelectedStepNames = allSelectedStepNames[0:-1]
              allSelectedTimePoints = allSelectedTimePoints[0:-2]
      else: #Then data posted
          allSelectedStepNames=postedData["args"][1]
          allSelectedTimePoints=postedData["args"][3]
          stepParameters=postedData["args"][5]

      if stepParameters: #make sure post is not empty
          if not userDefinedJobName:
              #userDefinedJobName = requestOutputJsonified["_id"]
              userDefinedJobName=""

          dataToPostToDB = {"jobName": userDefinedJobName,
                            "state": "NOT YET QUEUED",
                            "lightsheetCommit":currentLightsheetCommit,
                            "selectedStepNames": allSelectedStepNames,
                            "selectedTimePoints": allSelectedTimePoints,
                            "steps": stepParameters
                           }
          newId = lightsheetDB.jobs.insert_one(dataToPostToDB).inserted_id
          configAddress = settings.serverInfo['fullAddress'] + "config/" + str(newId)
          postBody = { "processingLocation": "LSF_JAVA",
                       "args": ["-configAddress",configAddress,
                                "-allSelectedStepNames",allSelectedStepNames,
                                "-allSelectedTimePoints",allSelectedTimePoints],
                       "resources": {"gridAccountId": "lightsheet"}
                   }
          requestOutput = requests.post(settings.devOrProductionJACS + '/async-services/lightsheetProcessing',
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

  parentJobInfo = getJobInfoFromDB(lightsheetDB, job_id,"parent")
  #Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                         title='Home',
                         pipelineSteps=pipelineSteps,
                         parentJobInfo = parentJobInfo,
                         logged_in=True,
                         config = config,
                         version = getAppVersion(app.root_path),
                         lightsheetDB_id = job_id)


@app.route('/job_status', methods=['GET'])
def job_status():
    before=datetime.now()
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet

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

@app.route('/config/<lightsheetDB_id>', methods=['GET'])
def config(lightsheetDB_id):
    stepName = request.args.get('stepName')
    output=getConfigurationsFromDB(lightsheetDB_id, client, stepName)
    if output==404:
        abort(404)
    else:
        return jsonify(output)