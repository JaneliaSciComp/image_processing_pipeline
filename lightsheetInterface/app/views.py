# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb, logging
from flask import render_template, request, jsonify, abort, send_from_directory
from flask import send_from_directory, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
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


ALLOWED_EXTENSIONS = set(['txt', 'json'])
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
# imageProcessingDB is the database containing lightsheet job information and parameters
imageProcessingDB = client.lightsheet


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')


# @app.route('/template/<template_name>', methods=['GET','POST'])
# def template(template_name):
#   imageProcessingDB_id = request.args.get('lightsheetDB_id')
#   if imageProcessingDB_id == 'favicon.ico':
#     imageProcessingDB_id = None
#   parentJobInfo = None
#   config = buildConfigObject(template_name)
#   currentTemplate = None
#   for template in config['templates']:
#     if template.name == template_name:
#       currentTemplate =  template_name
#       break;

#   parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id,"parent")
#   jobs = allJobsInJSON(imageProcessingDB)
#   return render_template('index.html',
#                        title='Home',
#                        pipelineSteps=None,
#                        parentJobInfo = parentJobInfo, # used by job status
#                        logged_in=True,
#                        config = config,
#                        lightsheetDB_id = None,
#                        jobsJson= jobs, # used by the job table
#                        submissionStatus = None,
#                        templates=config['templates'],
#                        currentTemplate=currentTemplate)

@app.route('/', methods=['GET','POST'], defaults={'template_name':None})
@app.route('/template/<template_name>', methods=['GET','POST'])
def index(template_name):
  submissionStatus = None
  imageProcessingDB_id = request.args.get('lightsheetDB_id')
  reparameterize = request.args.get('reparameterize');
  config = buildConfigObject(template_name)
  currentTemplate = None
  for template in config['templates']:
    if template.name == template_name:
      currentTemplate =  template_name
      break;
  if imageProcessingDB_id == 'favicon.ico':
    imageProcessingDB_id = None
  pipelineSteps = {}
  formData = None
  countJobs = 0
  jobData =  getJobStepData(imageProcessingDB_id, client) # get the data for all jobs
  ableToReparameterize=True
  succededButLatterStepFailed=[]
  globalParameters=None
  if jobData:
    globalParametersAndRemainingStepNames = list(imageProcessingDB.jobs.find({"_id":ObjectId(imageProcessingDB_id)},{"remainingStepNames":1,"globalParameters":1}))
    if "globalParameters" in globalParametersAndRemainingStepNames[0]:
      globalParameters = globalParametersAndRemainingStepNames[0]["globalParameters"]
    if ("pause" in jobData[-1]["parameters"] and jobData[-1]["parameters"]["pause"]==0 and jobData[-1]["state"]=="SUCCESSFUL") or any( (step["state"] in "RUNNING CREATED") for step in jobData):
      ableToReparameterize=False
    errorStepIndex = next((i for i,step in enumerate(jobData) if step["state"]=="ERROR"),None)
    if errorStepIndex:
      for i in range(errorStepIndex):
        succededButLatterStepFailed.append(jobData[i]["name"])
  if reparameterize=="true" and imageProcessingDB_id:
    reparameterize=True
    remainingStepNames=globalParametersAndRemainingStepNames[0]["remainingStepNames"]
    if not ableToReparameterize:
      abort(404)
  else:
    reparameterize=False

  # match data on step name
  matchNameIndex = {}
  if type(jobData) is list:
    if imageProcessingDB_id != None: # load data for an existing job
      for i in range(len(jobData)):
        if 'name' in jobData[i]:
          matchNameIndex[jobData[i]['name']] = i
      # go through all steps and find those, which are used by the current job
      for step in config['steps']:
        currentStep = step.name
        # If loading previous run parameters for specific step, then it should be checked sett editable
        if currentStep in matchNameIndex.keys() or currentStep=="globalParameters":
          editState = 'enabled'
          checkboxState = 'checked'
          stepData=None
          if currentStep =="globalParameters":
            if globalParameters:
              stepData = globalParameters
          else:
            stepData = jobData[matchNameIndex[currentStep]]
            if (reparameterize and currentStep not in remainingStepNames) or (currentStep in succededButLatterStepFailed):
              editState = 'disabled'
              checkboxState = 'unchecked'
          if stepData:
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
    app.logger.info('POST request root route -- json {0}'.format(request.json))
    #If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
    #imageProcessingDB is the database containing lightsheet job information and parameters
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
      globalParametersPosted = next((step["parameters"] for step in processedDataTemp if step["name"]=="globalParameters"),None)
      processedData=[]
      remainingStepNames=[];
      for step in config["steps"]: #Reorder json to get proper order and leave out global parameters
        stepName=step.name
        if "globalParameters" not in stepName:
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
      #Insert the data to the db
      # if reparameterize:
      #   imageProcessingDB_id=ObjectId(imageProcessingDB_id)
      #   subDict = {k: dataToPostToDB[k] for k in ('jobName', 'state', 'lightsheetCommit', 'remainingStepNames')}
      #   imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": subDict})
      #   for currentStepDictionary in processedData:
      #     imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id,"steps.name": currentStepDictionary["name"]},{"$set": {"steps.$":currentStepDictionary}})
      # else:
      #   imageProcessingDB_id = imageProcessingDB.jobs.insert_one(dataToPostToDB).inserted_id

      # if globalParametersPosted:
      #   globalParametersPosted.pop("")
      #   imageProcessingDB.jobs.update_one({"_id": imageProcessingDB_id},{"$set": {"globalParameters":globalParametersPosted}})

      # submissionStatus = submitToJACS(imageProcessingDB, imageProcessingDB_id, reparameterize)

  # updateDBStatesAndTimes(imageProcessingDB)
  parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id,"parent")
  jobs = allJobsInJSON(imageProcessingDB)
  #Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                       title='Home',
                       pipelineSteps=pipelineSteps,
                       parentJobInfo = parentJobInfo, # used by job status
                       logged_in=True,
                       config = config,
                       lightsheetDB_id = imageProcessingDB_id,
                       jobsJson= jobs, # used by the job table
                       submissionStatus = None,
                       currentTemplate=template_name)


@app.route('/job_status', methods=['GET','POST'])
def job_status():
    imageProcessingDB_id = request.args.get('lightsheetDB_id')
    #Mongo client
    updateDBStatesAndTimes(imageProcessingDB)
    parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "parent")
    childJobInfo=[]
    if request.method == 'POST':
      pausedJobInformation=list(imageProcessingDB.jobs.find({"_id":ObjectId(imageProcessingDB_id)}))
      pausedJobInformation=pausedJobInformation[0]
      pausedStates = [step['parameters']['pause'] for step in pausedJobInformation["steps"]]
      pausedStepIndex = next((i for i, pausable in enumerate(pausedStates) if pausable), None)
      pausedJobInformation["steps"][pausedStepIndex]["parameters"]["pause"] = 0
      while pausedJobInformation["remainingStepNames"][0]!=pausedJobInformation["steps"][pausedStepIndex]["name"]:
        pausedJobInformation["remainingStepNames"].pop(0)
      pausedJobInformation["remainingStepNames"].pop(0) #Remove steps that have been completed/approved
      imageProcessingDB.jobs.update_one({"_id": ObjectId(imageProcessingDB_id)},{"$set": pausedJobInformation})
      submissionStatus = submitToJACS(imageProcessingDB, imageProcessingDB_id, True)
      updateDBStatesAndTimes(imageProcessingDB)
    if imageProcessingDB_id is not None:
        childJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "child")
        childJobInfo = childJobInfo[0]["steps"]
    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentJobInfo=reversed(parentJobInfo), #so in chronolgical order
                           childJobInfo=childJobInfo,
                           logged_in=True,
                           lightsheetDB_id=imageProcessingDB_id)


@app.route('/search')
def search():
    return render_template('search.html')


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
                         form=form)


@app.route('/login')
def login():
  return render_template('login.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
  if request.method == 'GET':
    return render_template('upload.html')

  if request.method == 'POST':
    # check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_file(file.filename):
      filename = secure_filename(file.filename)
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
      return redirect(url_for('uploaded_file',
                             filename=filename))
    else:
      # allowed_ext = print(', '.join(ALLOWED_EXTENSIONS[:-1]) + " or " + ALLOWED_EXTENSIONS[-1])
      allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
      message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
      return  render_template('upload.html', message = message)
    return 'error'


@app.route('/upload/<filename>', methods=['GET', 'POST'])
def uploaded_file(filename):
      with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = createDBentries(c)
        return render_template('upload.html', content=c, filename=filename, message=result['message'], success=result['success'])
      message = []
      message.append('Error uploading the file {0}'.format(filename))
      return render_template('upload.html', filename=filename, message=message)
      # except BaseException as e:
      #   message = []
      #   message.append('There was an error uploading the file ' + filename + ": " + str(e))
      #   return render_template('upload.html', filename=filename, message=message)


@app.route('/config/<imageProcessingDB_id>', methods=['GET'])
def config(imageProcessingDB_id):
    globalParameter = request.args.get('globalParameter')
    stepName = request.args.get('stepName')
    stepParameter = request.args.get('stepParameter')
    output=getConfigurationsFromDB(imageProcessingDB_id, client, globalParameter, stepName, stepParameter)
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
