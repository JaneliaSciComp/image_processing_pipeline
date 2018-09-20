# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb, logging
from flask import render_template, request, jsonify, abort, send_from_directory
from flask import send_from_directory, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from app import app
from app.settings import Settings
from app.utils import *
from app.jobs_io import reformatDataToPost, parseJsonDataNoForms, doThePost
from app.models import Dependency, Configuration
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


@app.route('/step/<step_name>', methods=['GET','POST'])
def step(step_name):
  configObj = buildConfigObject()
  template_name = None
  reparameterize = None

  lightsheetDB_id = None
  currentStep = None
  for step in configObj['stepsAll']:
    if step.name == step_name:
      currentStep =  step_name

  if request.method == 'POST' and request.json:
    doThePost(request.json, reparameterize, imageProcessingDB, template_name)

  updateDBStatesAndTimes(imageProcessingDB)
  parentJobInfo = getJobInfoFromDB(imageProcessingDB, lightsheetDB_id, "parent")
  jobs = allJobsInJSON(imageProcessingDB)

  return render_template('index.html',
                       parentJobInfo = parentJobInfo, # used by job status
                       config = configObj,
                       jobsJson= jobs, # used by the job table
                       submissionStatus = None,
                       currentStep=currentStep,
                       currentTemplate=None
  )

@app.route('/template/<template_name>', methods=['GET','POST'])
def template(template_name):
  configObj = buildConfigObject()
  lightsheetDB_id = request.args.get('lightsheetDB_id')
  reparameterize = request.args.get('reparameterize');
  if lightsheetDB_id == 'favicon.ico':
    lightsheetDB_id = None
  parentJobInfo = None
  currentTemplate = None

  for template in configObj['templates']:
    if template.name == template_name:
      currentTemplate =  template_name
      break;

  if request.method == 'POST' and request.json:
    doThePost(request.json, reparameterize, imageProcessingDB, template_name)

  updateDBStatesAndTimes(imageProcessingDB)
  return render_template('index.html',
                       parentJobInfo = getJobInfoFromDB(imageProcessingDB, lightsheetDB_id, "parent"),
                       config = configObj,
                       jobsJson = allJobsInJSON(imageProcessingDB),
                       submissionStatus = None,
                       currentTemplate=currentTemplate)

@app.route('/', methods=['GET'])
def index():
  return redirect(url_for('template', template_name = "LightSheet"))

@app.route('/job/<image_db>', methods=['GET', 'POST'])
def load_job(image_db):
  configObj = buildConfigObject()
  submissionStatus = None
  imageProcessingDB_id = image_db
  reparameterize = request.args.get('reparameterize');

  template_name = None

  currentTemplate = None
 
  if imageProcessingDB_id == 'favicon.ico':
    imageProcessingDB_id = None

  pipelineSteps = {}
  formData = None
  countJobs = 0
  jobData =  getJobStepData(imageProcessingDB_id, client) # get the data for all jobs
  print(jobData)
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
      for step in configObj['stepsAll']:
        currentStep = step.name
        # If loading previous run parameters for specific step, then it should be checked sett editable
        if currentStep in matchNameIndex.keys() or currentStep=="globalParameters":
          editState = 'enabled'
          checkboxState = 'checked'
          stepData=None
          if currentStep =="globalParameters":
            continue
          else:
            stepData = jobData[matchNameIndex[currentStep]]
            if (reparameterize and currentStep not in remainingStepNames) or (currentStep in succededButLatterStepFailed):
              editState = 'disabled'
              checkboxState = 'unchecked'
          if stepData:
            jobs = parseJsonDataNoForms(stepData, currentStep, configObj)
            # Pipeline steps is passed to index.html for formatting the html based
            pipelineSteps[currentStep] = {
              'stepName': step.name,
              'stepDescription': step.description,
              'inputJson': None,
              'state': editState,
              'checkboxState': checkboxState,
              'jobs': jobs
            }
  elif type(jobData) is dict:
    submissionStatus = 'Job cannot be loaded.'

  if request.method == 'POST' and request.json:
    app.logger.info('POST request root route -- json {0}'.format(request.json))
    doThePost(request.json, reparameterize, imageProcessingDB, imageProcessingDB_id, request.base_url,template_name)

  updateDBStatesAndTimes(imageProcessingDB)
  #Return index.html with pipelineSteps and serviceData
  return render_template('index.html',
                       pipelineSteps=pipelineSteps,
                       parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "parent"),
                       jobsJson = allJobsInJSON(imageProcessingDB),
                       config = configObj,
                       lightsheetDB_id = imageProcessingDB_id,
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
    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentJobInfo=reversed(parentJobInfo), #so in chronolgical order
                           childJobInfo=childJobInfo,
                           logged_in=True,
                           lightsheetDB_id=imageProcessingDB_id)

@app.route('/load/<config_name>', methods=['GET'])
def load_configuration(config_name):
  configObj = buildConfigObject();
  pInstance = PipelineInstance.objects.filter(name=config_name).first();
  ipdb.set_trace()
  if pInstance:
    print(pInstance.content)
    return render_template('index.html',
              configurations = pipeline_config,
              parentJobInfo = getJobInfoFromDB(imageProcessingDB, None, "parent"),
              jobsJson = allJobsInJSON(imageProcessingDB),
              config = configObj,
      )
  return 'test'

def buildTemplateSteps(configObj):
  for step in configObj['stepsAll']:
        currentStep = step.name
        # If loading previous run parameters for specific step, then it should be checked sett editable
        if currentStep in matchNameIndex.keys() or currentStep=="globalParameters":
          editState = 'enabled'
          checkboxState = 'checked'
          stepData=None
          if currentStep =="globalParameters":
            continue
          else:
            stepData = jobData[matchNameIndex[currentStep]]
            if (reparameterize and currentStep not in remainingStepNames) or (currentStep in succededButLatterStepFailed):
              editState = 'disabled'
              checkboxState = 'unchecked'
          if stepData:
            jobs = parseJsonDataNoForms(stepData, currentStep, configObj)
            # Pipeline steps is passed to index.html for formatting the html based
            pipelineSteps[currentStep] = {
              'stepName': step.name,
              'stepDescription': step.description,
              'inputJson': None,
              'state': editState,
              'checkboxState': checkboxState,
              'jobs': jobs
            }

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
def uploaded_file(filename = None):
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

@app.route('/upload_config', methods=['GET', 'POST'])
def upload_config(filename = None):
  if request.method == 'GET':
    return render_template('upload_config.html')
  # Handle uploaded file
  if request.method == "POST":
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
      return redirect(url_for('uploaded_configfile',
                             filename=filename))
    else:
      # allowed_ext = print(', '.join(ALLOWED_EXTENSIONS[:-1]) + " or " + ALLOWED_EXTENSIONS[-1])
      allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
      message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
      return  render_template('upload.html', message = message)
    return 'error'

@app.route('/upload_conf/<filename>', methods=['GET', 'POST'])
def uploaded_configfile(filename = None):
  with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
    c = json.loads(file.read())
    result = createConfig(c)
    return render_template('upload.html', content=c, filename=filename, message=result['message'], success=result['success'])
  message = []
  message.append('Error uploading the file {0}'.format(filename))
  return render_template('upload.html', filename=filename, message=message)

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

@app.route('/test')
def test():
  return 'test'

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
