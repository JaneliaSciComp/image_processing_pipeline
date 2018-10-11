# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb, logging
from flask import render_template, request, jsonify, abort, send_from_directory
from flask import send_from_directory, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from app import app
from app.settings import Settings
from app.utils import *
from app.jobs_io import reformatDataToPost, parseJsonDataNoForms, doThePost, loadPreexistingJob
from app.models import Dependency, Configuration
from bson.objectid import ObjectId
from pprint import pprint

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
  stepOrTemplateName = "Step: " + step_name
  configObj = buildConfigObject()
  lightsheetDB_id = request.args.get('lightsheetDB_id')
  reparameterize = request.args.get('reparameterize');
  if lightsheetDB_id == 'favicon.ico':
    lightsheetDB_id = None

  submissionStatus = None;
  pipelineSteps = None;
  
  if request.method == 'POST' and request.json:
    doThePost(request.json, reparameterize, imageProcessingDB, lightsheetDB_id, None, stepOrTemplateName)

  if lightsheetDB_id:
    pipelineSteps, submissionStatus = loadPreexistingJob(imageProcessingDB, lightsheetDB_id, reparameterize, configObj);

  updateDBStatesAndTimes(imageProcessingDB)
  jobs = allJobsInJSON(imageProcessingDB)

  return render_template('index.html',
                       pipelineSteps = pipelineSteps,
                       config = configObj,
                       jobsJson = jobs, # used by the job table
                       submissionStatus = None,
                       currentStep = step_name,
                       currentTemplate = None
  )

@app.route('/template/<template_name>', methods=['GET','POST'])
def template(template_name):
  stepOrTemplateName = "Template: " + template_name
  configObj = buildConfigObject()
  lightsheetDB_id = request.args.get('lightsheetDB_id')
  reparameterize = request.args.get('reparameterize');
  if lightsheetDB_id == 'favicon.ico':
    lightsheetDB_id = None

  submissionStatus = None;
  pipelineSteps = None;
  
  if request.method == 'POST' and request.json:
    doThePost(request.json, reparameterize, imageProcessingDB, lightsheetDB_id, None, stepOrTemplateName)

  if lightsheetDB_id:
    pipelineSteps, submissionStatus = loadPreexistingJob(imageProcessingDB, lightsheetDB_id, reparameterize, configObj);

  updateDBStatesAndTimes(imageProcessingDB)
  return render_template('index.html',
                       pipelineSteps=pipelineSteps,
                       parentJobInfo = None,
                       config = configObj,
                       jobsJson = allJobsInJSON(imageProcessingDB),
                       submissionStatus = submissionStatus,
                       currentTemplate=template_name)

@app.route('/', methods=['GET'])
def index():
  return redirect(url_for('template', template_name = "LightSheet"))

@app.route('/job_status', methods=['GET','POST'])
def job_status():
    imageProcessingDB_id = request.args.get('lightsheetDB_id')
    #Mongo client
    updateDBStatesAndTimes(imageProcessingDB)
    parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "parent")
    childJobInfo=[]
    jobType = []
    stepOrTemplateName=[]
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
        jobType, stepOrTemplateName, childJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "child")
    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentJobInfo=reversed(parentJobInfo), #so in chronolgical order
                           childJobInfo=childJobInfo,
                           lightsheetDB_id=imageProcessingDB_id,
                           stepOrTemplateName = stepOrTemplateName,
                           jobType = jobType)


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
    return redirect(url_for('load_configuration', config_name = result['name']))
    #return render_template('upload.html', content=c, filename=filename, message=result['message'], success=result['success'])
  message = []
  message.append('Error uploading the file {0}'.format(filename))
  ##return render_template('upload.html', filename=filename, message=message)

@app.route('/load/<config_name>', methods=['GET', 'POST'])
def load_configuration(config_name):
  configObj = buildConfigObject();
  pInstance = PipelineInstance.objects.filter(name=config_name).first();
  if pInstance:
    content = json.loads(pInstance.content)
    pipelineSteps = {}

    if 'steps' in content:
      steps = content['steps']

      for s in steps:
        name = s['name']
        jobs = parseJsonDataNoForms(s, name, configObj)
        # Pipeline steps is passed to index.html for formatting the html based
        pipelineSteps[name] = {
          'stepName': name,
          'stepDescription': configObj['stepsAllDict'][name].description,
          'inputJson': None,
          'state': False,
          'checkboxState': 'unchecked',
          'jobs': jobs
        }

    if request.method == 'POST' and request.json:
      doThePost(request.json, None, imageProcessingDB, None)

    return render_template('index.html',
      pipelineSteps = pipelineSteps,
      pipeline_config = config_name,
      parentJobInfo = None,
      jobsJson = allJobsInJSON(imageProcessingDB),
      config = configObj,
    )

  return 'No such configuration in the system.'

@app.route('/config/<imageProcessingDB_id>', methods=['GET'])
def config(imageProcessingDB_id):
    globalParameter = request.args.get('globalParameter')
    stepName = request.args.get('stepName')
    stepParameter = request.args.get('stepParameter')
    output=getConfigurationsFromDB(imageProcessingDB_id, imageProcessingDB, globalParameter, stepName, stepParameter)
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
