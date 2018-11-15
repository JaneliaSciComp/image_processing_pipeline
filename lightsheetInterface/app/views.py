# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb, logging, time
from flask import render_template, request, jsonify, abort, send_from_directory, Response
from flask import send_from_directory, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from app import app
from app.authservice import create_auth_service
from app.forms import LoginForm
from app.utils import *
from app.jobs_io import reformatDataToPost, parseJsonDataNoForms, doThePost, loadPreexistingJob
from app.models import Dependency, Configuration
from bson.objectid import ObjectId
from collections import OrderedDict

ALLOWED_EXTENSIONS = set(['txt', 'json'])

global_error = None

# Mongo client
mongo_uri = app.config['MONGODB_HOST']
mongo_user = app.config.get('MONGODB_USERNAME')
mongo_password = app.config.get('MONGODB_PASSWORD')

# JACS server
jacs_host = app.config.get('JACS_HOST')

if mongo_user:
    client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
else:
    client = MongoClient(mongo_uri)

# imageProcessingDB is the database containing lightsheet job information and parameters
imageProcessingDB = client.lightsheet

# All step names and globalParameters and nonGlobalParameters for current config
allStepNames = []
globalParameters = []
nonGlobalParameters = []

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    auth_service = create_auth_service()
    auth_service.logout()
    return redirect(url_for('.index'))


@app.route('/step/<step_name>', methods=['GET', 'POST'])
@login_required
def step(step_name):
    stepOrTemplateName = "Step: " + step_name
    configObj = buildConfigObject()
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    reparameterize = request.args.get('reparameterize')
    if lightsheetDB_id == 'favicon.ico':
        lightsheetDB_id = None

    submissionStatus = None
    pipelineSteps = None
    jobName = None
    posted = "false"
    if request.method == 'POST':
        posted = "true"
        if request.json:
            submissionStatus = doThePost(request.url_root, request.json, reparameterize, imageProcessingDB,
                                         lightsheetDB_id,
                                         None, stepOrTemplateName)
        else:
            time.sleep(0.5)
    if lightsheetDB_id:
        pipelineSteps, loadStatus, jobName = loadPreexistingJob(imageProcessingDB, lightsheetDB_id, reparameterize,
                                                                configObj)

    updateDBStatesAndTimes(imageProcessingDB)
    jobs = allJobsInJSON(imageProcessingDB)
    global allStepNames
    allStepNames = step_name
    return render_template('index.html',
                           pipelineSteps=pipelineSteps,
                           config=configObj,
                           jobsJson=jobs,  # used by the job table
                           submissionStatus=None,
                           currentStep=step_name,
                           currentTemplate=None,
                           posted=posted,
                           jobName=jobName,
                           jacs_host = jacs_host)


@app.route('/template/<template_name>', methods=['GET', 'POST'])
@login_required
def template(template_name):
    stepOrTemplateName = "Template: " + template_name
    configObj = buildConfigObject()
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    reparameterize = request.args.get('reparameterize')
    if lightsheetDB_id == 'favicon.ico':
        lightsheetDB_id = None

    submissionStatus = None
    pipelineSteps = None
    jobName = None
    posted = "false"
    if request.method == 'POST':
        posted = "true"
        if request.json:
            submissionStatus = doThePost(request.url_root, request.json, reparameterize, imageProcessingDB,
                                         lightsheetDB_id,
                                         None,
                                         stepOrTemplateName)
        else:
            time.sleep(0.5)
    if lightsheetDB_id:
        pipelineSteps, loadStatus, jobName = loadPreexistingJob(imageProcessingDB, lightsheetDB_id, reparameterize,
                                                                configObj)

    global allStepNames, globalParameters, nonGlobalParameters
    allStepNames = []
    globalParameters = []
    nonGlobalParameters = []
    if configObj.get('steps'):
        # only populate step names if steps is set
        if template_name in configObj["steps"]:
            for step in configObj["steps"][template_name]:
                allStepNames.append(step.name)
                if "GLOBALPARAMETERS" in step.name.upper():
                    globalParameters = [parameter.name for parameter in step.parameter]
                else:
                    nonGlobalParameters=nonGlobalParameters+ [parameter.name for parameter in step.parameter]
        else: #old template name or something
            for stepName in pipelineSteps:
                allStepNames.append(stepName)
                if "GLOBALPARAMETERS" in stepName.upper():
                    globalParameters = [parameter.name for parameter in configObj["stepsAllDict"][stepName].parameter]
                else:
                    nonGlobalParameters=nonGlobalParameters + [parameter.name for parameter in configObj["stepsAllDict"][stepName].parameter]
    updateDBStatesAndTimes(imageProcessingDB)
    return render_template('index.html',
                           pipelineSteps=pipelineSteps,
                           parentJobInfo=None,
                           config=configObj,
                           jobsJson=allJobsInJSON(imageProcessingDB),
                           submissionStatus=submissionStatus,
                           currentTemplate=template_name,
                           posted=posted,
                           jobName=jobName,
                           jacs_host = jacs_host)


@app.route('/', methods=['GET'])
@login_required
def index():
    return redirect(url_for('template', template_name="LightSheet"))


@app.route('/job_status', methods=['GET', 'POST'])
@login_required
def job_status():
    submissionStatus = None
    imageProcessingDB_id = request.args.get('lightsheetDB_id')
    # Mongo client
    updateDBStatesAndTimes(imageProcessingDB)
    parentJobInfo = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "parent")
    childJobInfo = []
    jobType = []
    stepOrTemplateName = []
    posted="false"
    remainingStepNames = None
    if request.method == 'POST':
        #Find pause that is in remaining steps
        posted = "true"
        pausedJobInformation = list(imageProcessingDB.jobs.find({"_id": ObjectId(imageProcessingDB_id)}))
        pausedJobInformation = pausedJobInformation[0]
        # Make sure that we pop off all steps that have completed and been approved, ie, ones that are no longer in remaining
        pausedStates = [step['parameters']['pause'] if ('pause' in step['parameters'] and step["name"] in pausedJobInformation["remainingStepNames"]) else 0 for step in pausedJobInformation["steps"]]
        pausedStepIndex = next((i for i, pausable in enumerate(pausedStates) if pausable), None)
        while pausedJobInformation["remainingStepNames"][0] != pausedJobInformation["steps"][pausedStepIndex]["name"]:
             pausedJobInformation["remainingStepNames"].pop(0)
        pausedJobInformation["remainingStepNames"].pop(0)  # Remove steps that have been completed/approved
        imageProcessingDB.jobs.update_one({"_id": ObjectId(imageProcessingDB_id)}, {"$set": pausedJobInformation})
        if pausedJobInformation["remainingStepNames"]: #only submit if not empty
            submissionStatus = submitToJACS(request.url_root, imageProcessingDB, imageProcessingDB_id, True)
        time.sleep(0.5)
        updateDBStatesAndTimes(imageProcessingDB)
    if imageProcessingDB_id is not None:
        jobType, stepOrTemplateName, childJobInfo, remainingStepNames = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "child")
        if not stepOrTemplateName:
            stepOrTemplateName = "/load/previousjob"
    # Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html',
                           parentJobInfo=reversed(parentJobInfo),  # so in chronolgical order
                           childJobInfo=childJobInfo,
                           lightsheetDB_id=imageProcessingDB_id,
                           stepOrTemplateName=stepOrTemplateName,
                           submissionStatus=submissionStatus,
                           jobType=jobType,
                           posted=posted,
                           jacs_host=jacs_host,
                           remainingStepNames = remainingStepNames)


@app.route('/search')
@login_required
def search():
    return render_template('search.html')


@app.route('/login_form')
def login_form():
    next_page_param = request.args.get('next')
    form = LoginForm(csrf_enabled=True)
    return render_template('login.html',
                           form=form,
                           next=next_page_param if next_page_param else '')


@app.route('/login', methods=['POST'])
def login():
    if request.args.get('next'):
        next_page = request.args.get('next')
    elif request.form.get('next'):
        next_page = request.form.get('next')
    else:
        next_page = url_for('.index')
    form = LoginForm(csrf_enabled=True)
    if not form.validate_on_submit():
        return render_template('login.html',
                               form=form,
                               next=next_page if next_page else ''), 401
    # execute login
    auth_service = create_auth_service()
    authenticated = auth_service.authenticate({'username': form.username.data, 'password': form.password.data})
    if authenticated:
        return redirect(next_page)
    else:
        return render_template('login.html',
                               form=form,
                               next=next_page if next_page else ''), 401


@app.route('/upload', methods=['GET', 'POST'])
@login_required
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
        if file and _allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_file',
                                    filename=filename))
        else:
            # allowed_ext = print(', '.join(ALLOWED_EXTENSIONS[:-1]) + " or " + ALLOWED_EXTENSIONS[-1])
            allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
            message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
            return render_template('upload.html', message=message)
        return 'error'


@app.route('/upload/<filename>', methods=['GET', 'POST'])
@login_required
def uploaded_file(filename=None):
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = createDBentries(c)
        return render_template('upload.html', content=c, filename=filename, message=result['message'],
                               success=result['success'])
    message = []
    message.append('Error uploading the file {0}'.format(filename))
    return render_template('upload.html', filename=filename, message=message)


@app.route('/upload_config', methods=['GET', 'POST'])
@login_required
def upload_config(filename=None):
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
        if file and _allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_configfile',
                                    filename=filename))
        else:
            # allowed_ext = print(', '.join(ALLOWED_EXTENSIONS[:-1]) + " or " + ALLOWED_EXTENSIONS[-1])
            allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
            message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
            return render_template('upload.html', message=message)
        return 'error'


@app.route('/upload_conf/<filename>', methods=['GET', 'POST'])
@login_required
def uploaded_configfile(filename=None):
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = createConfig(c)
        return redirect(url_for('load_configuration', config_name=result['name']))
        # return render_template('upload.html', content=c, filename=filename, message=result['message'], success=result['success'])
    message = []
    message.append('Error uploading the file {0}'.format(filename))
    ##return render_template('upload.html', filename=filename, message=message)


@app.route('/load/<config_name>', methods=['GET', 'POST'])
@login_required
def load_configuration(config_name):
    configObj = buildConfigObject()
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    reparameterize = request.args.get('reparameterize')
    if lightsheetDB_id == 'favicon.ico':
        lightsheetDB_id = None
    currentStep = None
    currentTemplate = None
    pInstance = PipelineInstance.objects.filter(name=config_name).first()
    global allStepNames, globalParameters, nonGlobalParameters
    stepOrTemplateName = None
    allStepNames = []
    globalParameters = []
    nonGlobalParameters = []
    jobName = None
    if lightsheetDB_id or pInstance:  # Then a previously submitted job is loaded
        if lightsheetDB_id:
            pipelineSteps, submissionStatus, jobName = loadPreexistingJob(imageProcessingDB, lightsheetDB_id,
                                                                          reparameterize, configObj)
            for stepName in pipelineSteps:
                allStepNames.append(stepName)

        else:
            content = json.loads(pInstance.content)
            pipelineSteps = OrderedDict()
            if 'steps' in content:
                steps = content['steps']
                for s in steps:
                    name = s['name']
                    allStepNames.append(name)
                    jobs = parseJsonDataNoForms(s, name, configObj)
                    # Pipeline steps is passed to index.html for formatting the html based
                    pipelineSteps[name] = {
                        'stepName': name,
                        'stepDescription': configObj['stepsAllDict'][name].description,
                        'inputJson': None,
                        'state': False,
                        'checkboxState': 'checked',
                        'collapseOrShow': 'show',
                        'jobs': jobs
                    }
                    if "GLOBALPARAMETERS" in name.upper():
                        globalParameters = [parameter.name for parameter in configObj["stepsAllDict"][name].parameter]
                    else:
                        nonGlobalParameters=nonGlobalParameters + [parameter.name for parameter in configObj["stepsAllDict"][name].parameter]

        if "stepOrTemplateName" in content:
                stepOrTemplateName = content["stepOrTemplateName"]
                if stepOrTemplateName.find("Step: ", 0, 6) != -1:
                    currentStep = stepOrTemplateName[6:]
                else:
                    currentTemplate = stepOrTemplateName[10:]
        posted = "false"
        if request.method == 'POST':
            posted = "true"
            if request.json:
                doThePost(request.url_root, request.json, reparameterize, imageProcessingDB, lightsheetDB_id, None,
                          stepOrTemplateName)
            else:
                time.sleep(0.5)

        updateDBStatesAndTimes(imageProcessingDB)
        return render_template('index.html',
                               pipelineSteps=pipelineSteps,
                               pipeline_config=config_name,
                               parentJobInfo=None,
                               jobsJson=allJobsInJSON(imageProcessingDB),
                               config=configObj,
                               currentStep=currentStep,
                               currentTemplate=currentTemplate,
                               posted=posted,
                               jobName=None
                               )

        updateDBStatesAndTimes(imageProcessingDB)
        return 'No such configuration in the system.'


@app.route('/config/<imageProcessingDB_id>', methods=['GET'])
def config(imageProcessingDB_id):
    globalParameter = request.args.get('globalParameter')
    stepName = request.args.get('stepName')
    stepParameter = request.args.get('stepParameter')
    output = getConfigurationsFromDB(imageProcessingDB_id, imageProcessingDB, globalParameter, stepName, stepParameter)
    if output == 404:
        abort(404)
    else:
        return jsonify(output)


@app.route('/download_settings/<unique_id>', methods=['GET', 'POST'])
@login_required
def download_settings(unique_id):
    unique_id = int(unique_id)
    if request.method == 'POST':
        stepOrTemplateName = request.args.get('stepOrTemplateName')
        postedJson = request.json
        jobName = ''
        if 'jobName' in postedJson.keys():
            jobName = postedJson['jobName']
            del (postedJson['jobName'])
        reformattedData = reformatDataToPost(postedJson, False)
        reformattedData = {'username': current_user.username,
                           'unique_id': unique_id,
                           'name': jobName,
                           'stepOrTemplateName': stepOrTemplateName,
                           'steps': reformattedData[0],
                           }
        imageProcessingDB.downloadSettings.insert_one(reformattedData)
        return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}
    else:
        time.sleep(0.5)
        output = list(
            imageProcessingDB.downloadSettings.find({"unique_id": unique_id, 'username': current_user.username},
                                                    {"_id": 0, "unique_id": 0, "username": 0}))
        output = output[0]
        name = output['name']
        imageProcessingDB.downloadSettings.delete_many({'username': current_user.username})
        # imageProcessingDB.downloadSettings.delete_one({"unique_id": unique_id})
        return Response(json.dumps(OrderedDict(output), indent=2, separators=(',', ': ')),
                        mimetype='application/json',
                        headers={"Content-Disposition": "attachment;filename=" + name + ".json"})


@app.route('/delete_entries/', methods=['POST'])
@login_required
def delete_entries():
    ids_to_delete = request.json
    for i, id_to_delete in enumerate(ids_to_delete):
        ids_to_delete[i] = ObjectId(id_to_delete)
    imageProcessingDB.jobs.delete_many({"username": current_user.username, "_id": {"$in": ids_to_delete}})
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


def createDependencyResults(dependencies):
    result = []
    for d in dependencies:
        inputFieldName = d.inputField.name
        outputFieldName = d.outputField.name
        if inputFieldName in globalParameters and outputFieldName in nonGlobalParameters:
        # #     # need to check here, if simple value transfer (for string or float values) or if it's a nested field
              obj = {}
              obj['input'] = d.inputField.name if d.inputField and d.inputField.name is not None else ''
              obj['output'] = d.outputField.name if d.outputField and d.outputField.name is not None else ''
              obj['pattern'] = d.pattern if d.pattern is not None else ''
              obj['formatting'] = d.inputField.formatting if d.inputField.formatting is not None else ''
              obj['step']=outputFieldName.split("_")[-1]
              result.append(obj)
    return result


@app.context_processor
def add_value_dependency_object():
    dep = Dependency.objects.filter(dependency_type='V')
    result = []
    if dep is not None:
        result = createDependencyResults(dep)
    return dict(value_dependency=result)


@app.context_processor
def add_dimension_dependency_object():
    dep = Dependency.objects.filter(dependency_type='D')
    result = []
    if dep is not None:
        result = createDependencyResults(dep)
    return dict(dimension_dependency=result)
