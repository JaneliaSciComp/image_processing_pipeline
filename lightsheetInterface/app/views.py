<<<<<<< HEAD
import requests, json, datetime, bson, subprocess, re, math
from flask import render_template, request, jsonify, abort
=======
import requests, json, os, math, datetime, bson, re, subprocess, ipdb
from flask import render_template, request, abort
>>>>>>> origin
from pymongo import MongoClient
from collections import OrderedDict
from datetime import datetime
from app import app
from app.settings import Settings
<<<<<<< HEAD
from app.models import AppConfig
from app.utils import buildConfigObject, eastern, UTC
from app.utils import updateDBStatesAndTimes, getJobInfoFromDB, getConfigurationsFromDB, getHeaders, loadParameters, getAppVersion, parseJsonData
from bson.objectid import ObjectId
=======
from app.utils import *
>>>>>>> origin

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

<<<<<<< HEAD
app_version = getAppVersion(app.root_path)
=======
app.route('/register', methods=['GET', 'POST'])

>>>>>>> origin

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


@app.route('/job/<job_id>', methods=['GET', 'POST'])
def load_job(job_id):
  config = buildConfigObject()
  if job_id == 'favicon.ico':
    job_id = None

  pipelineSteps = {}
  formData = None
  countJobs = 0
  # go through all steps and find those, which are used by the current job
  for step in config['steps']:
    currentStep = step.name
    configData = getConfigurationsFromDB(job_id, client, currentStep)
    print(configData)
    if configData != None and job_id != None:
      # If loading previous run parameters for specific step, then it should be checked and editable
      editState = 'enabled'
      checkboxState = 'checked'
      countJobs += 1
      forms = parseJsonData(configData)
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
<<<<<<< HEAD
        keys = request.form.keys()
        for k in iter(keys):
            print(k)
    return 'form submitted'

@app.route('/', methods=['GET','POST'])
def index():
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet
    if lightsheetDB_id is not None:
        jobSelected=True
        childJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id, "child", True)
        childJobInfo = childJobInfo[0]
        arrayOfStepDictionaries = childJobInfo["steps"]
    else:
        jobSelected=False
    #Mongo client
    config = buildConfigObject()
    #index is the function to execute when url '/' or '/<lightsheetDB_id>' is reached and takes in the currently selected job index, if any

    #For each step, load either the default json files or the stored json files from a previously selected run
    pipelineSteps = []
    jobStepIndex = 0
    for step in config['steps']:
        currentStep = step.name
        #Check if currentStep was used in previous service
        if jobSelected and (currentStep in childJobInfo["selectedStepNames"]):
            #If loading previous run parameters for specific step, then it should be checked and editable
            editState = 'enabled'
            checkboxState = 'checked'
            jsonString = json.dumps(arrayOfStepDictionaries[jobStepIndex]["parameters"], indent=4, separators=(',', ': '));
            jobStepIndex = jobStepIndex+1
            formObject = {}
        else: #Defaults
            editState = 'disabled'
            checkboxState = ''
            jsonData = getConfigurationsFromDB("templateConfigurations", currentStep) 
            formObject = {}
            formObject['step'] = step
            formData = parseJsonData(jsonData)
            formObject['forms'] = formData # get the form data separated into tabs for frequent / sometimes / rare
            #Reformat json data into a more digestable format
            jsonString = json.dumps(jsonData, indent=4, separators=(',', ': '))

        jsonString = re.sub(r'\[.*?\]', lambda m: m.group().replace("\n", ""), jsonString, flags=re.DOTALL)
        jsonString = re.sub(r'\[.*?\]', lambda m: m.group().replace(" ", ""), jsonString, flags=re.DOTALL)

        #Pipeline steps is passed to index.html for formatting the html based
        pipelineSteps.append({
            'stepName': currentStep,
            'stepDescription':step.description,
            'inputJson': jsonString,
            'state': editState,
            'checkboxState': checkboxState
        })

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
    parentJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id,"parent")
  
    #Return index.html with pipelineSteps and serviceData
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           parentJobInfo = parentJobInfo,
                           logged_in=True,
                           config = config,
                           version = app_version,
                           formData = formObject,
                           lightsheetDB_id = lightsheetDB_id)
=======
      # If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
      # lightsheetDB is the database containing lightsheet job information and parameters
      numSteps = 0
      allSelectedStepNames = ""
      allSelectedTimePoints = ""
      stepParameters = []

      userDefinedJobName = []
      for currentStep in config['steps']:
        text = request.form.get(currentStep)  # will be none if checkbox is not checked
        if text is not None:
          if numSteps == 0:
            # Create new document in jobs collection in lightsheet database and create json output directory
            newId = lightsheetDB.jobs.insert_one({"steps": {}}).inserted_id
            outputDirectory = outputDirectoryBase + str(newId) + "/"
            postBody = {"processingLocation": "LSF_JAVA",
                        "args": ["-configDirectory", outputDirectory],
                        "resources": {"gridAccountId": "lightsheet"}
                        # ,"queueId":"jacs-dev"
                        }
            os.mkdir(outputDirectory)
          # Write json files
          fileName = str(numSteps) + "_" + currentStep + ".json"
          fh = open(outputDirectory + fileName, "w")
          fh.write(text)
          fh.close()
          # Store step parameters and step names/times to use as arguments for the post
          jsonifiedText = json.loads(text, object_pairs_hook=OrderedDict)
          stepParameters.append({"stepName": currentStep, "parameters": jsonifiedText})
          numTimePoints = math.ceil(1 + (jsonifiedText["timepoints"]["end"] - jsonifiedText["timepoints"]["start"]) /
                                    jsonifiedText["timepoints"]["every"])
          allSelectedStepNames = allSelectedStepNames + currentStep + ","
          allSelectedTimePoints = allSelectedTimePoints + str(numTimePoints) + ", "
          numSteps += 1

      if numSteps > 0:
        # Finish preparing the post body
        allSelectedStepNames = allSelectedStepNames[0:-1]
        allSelectedTimePoints = allSelectedTimePoints[0:-2]
        postBody["args"].extend(("-allSelectedStepNames", allSelectedStepNames))
        postBody["args"].extend(("-allSelectedTimePoints", allSelectedTimePoints))

        # Post to JACS
        requestOutput = requests.post(settings.devOrProductionJACS + '/async-services/lightsheetProcessing',
                                      headers=getHeaders(),
                                      data=json.dumps(postBody))

        requestOutputJsonified = requestOutput.json()
        # Store information about the job in the lightsheet database
        currentLightsheetCommit = subprocess.check_output(
          ['git', '--git-dir', settings.pipelineGit, 'rev-parse', 'HEAD']).strip().decode("utf-8")
        if not userDefinedJobName:
          userDefinedJobName = requestOutputJsonified["_id"]

        lightsheetDB.jobs.update_one({"_id": newId},
                                     {"$set": {"jacs_id": requestOutputJsonified["_id"], "jobName": userDefinedJobName,
                                               "lightsheetCommit": currentLightsheetCommit,
                                               "jsonDirectory": outputDirectory,
                                               "selectedStepNames": allSelectedStepNames, "steps": stepParameters}})


        # Give the user the ability to define local jobs, for development purposes for instance
        # if hasattr(settings, 'localJobs') and len(settings.localJobs) > 0:
        #     for job in settings.localJobs:
        # jobData = loadJobDataFromLocal(job)
        # formData = parseJsonData(jobData)
        # parentServiceData.append(jobData)

  # Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                         pipelineSteps=pipelineSteps,
                         logged_in=True,
                         config=config,
                         version=getAppVersion(app.root_path),
                         jobIndex=job_id)


@app.route('/', methods=['GET'])
def index():
  lightsheetDB_id = request.args.get('lightsheetDB_id')
  config = buildConfigObject()
  parentJobInfo = getJobInfoFromDB(lightsheetDB, lightsheetDB_id,"parent")

  # Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                         steps=config['steps'],
                         parentJobInfo = parentJobInfo,
                         logged_in=True,
                         config=config,
                         version=getAppVersion(app.root_path))

>>>>>>> origin

@app.route('/job_status', methods=['GET'])
def job_status():
<<<<<<< HEAD
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
                           version = app_version)
@app.route('/search')
def search():
    return render_template('search.html',
                           logged_in=True,
                           version = app_version)

@app.route('/config/<lightsheetDB_id>', methods=['GET'])
def config(lightsheetDB_id):
    stepName = request.args.get('stepName')
    output=getConfigurationsFromDB(lightsheetDB_id, stepName)
    if output==404:
        abort(404)
    else:
        return jsonify(output)
=======
  jobIndex = request.args.get('jacsServiceIndex')
  # Mongo client
  client = MongoClient(settings.mongo)
  # lightsheetDB is the database containing lightsheet job information and parameters
  lightsheetDB = client.lightsheet

  # For now, get information from jacs database directly to monitor parent and child job statuses
  parentServiceData = getParentServiceDataFromJACS(lightsheetDB, jobIndex)
  childSummarizedStatuses = []

  if jobIndex is not None:
    jobIndex = int(jobIndex)

    # If a specific parent job is selected, find all the child job status information and store the step name, status, start time, endtime and elapsedTime
    childJobStatuses = getChildServiceDataFromJACS(parentServiceData[jobIndex]["_id"])
    steps = parentServiceData[jobIndex]["args"][3].split(",")
    for i in range(0, len(steps)):
      if i <= len(childJobStatuses) - 1:
        childSummarizedStatuses.append({"step": steps[i], "status": childJobStatuses[i]["state"],
                                        "startTime": str(childJobStatuses[i]["creationDate"]),
                                        "endTime": str(childJobStatuses[i]["modificationDate"]),
                                        "elapsedTime": str(
                                          childJobStatuses[i]["modificationDate"] - childJobStatuses[i][
                                            "creationDate"])})
        if childJobStatuses[i]["state"] == "RUNNING":
          childSummarizedStatuses[i]["elapsedTime"] = str(
            datetime.now(utils.eastern) - childJobStatuses[i]["creationDate"])
      else:
        childSummarizedStatuses.append(
          {"step": steps[i], "status": "NOT YET QUEUED", "startTime": "N/A", "endTime": "N/A", "elapsedTime": "N/A"})

  # Return job_status.html which takes in parentServiceData and childSummarizedStatuses
  return render_template('job_status.html',
                         parentServiceData=parentServiceData,
                         childSummarizedStatuses=childSummarizedStatuses,
                         logged_in=True,
                         version=getAppVersion(app.root_path))


@app.route('/config/<_id>', methods=['GET'])
def config(_id):
  stepName = request.args.get('stepName')
  output = getConfigurationsFromDB(_id, client, stepName)
  if output == 404:
    abort(404)
  else:
    return jsonify(output)


@app.route('/search')
def search():
  return render_template('search.html',
                         logged_in=True,
                         version=getAppVersion(app.root_path))

# @app.errorhandler(404)
# def error_page(error):
#     err = 'There was an error using that page. Please make sure, you are connected to the internal network of '
#     err += 'Janelia and check with SciComp, if the application is configured correctly.';
#     if global_error != None:
#         err += '\n' + global_error
#     return render_template('error.html', err=err), 404
>>>>>>> origin
