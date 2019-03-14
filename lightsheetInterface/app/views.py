# Contains routes and functions to pass content to the template layer
import requests, json, os, math, bson, re, subprocess, ipdb, logging, time
from flask import render_template, request, jsonify, abort, send_from_directory, Response, flash
from flask import send_from_directory, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from app import app
from app.authservice import create_auth_service
from app.forms import LoginForm
from app.utils import *
from app.jobs_io import reformatDataToPost, parseJsonDataNoForms, doThePost, loadPreexistingJob, loadUploadedConfig
from app.models import Dependency, Configuration
from bson.objectid import ObjectId
from collections import OrderedDict

# This file contains all the view components necessary for routing and loading the correct webpages


ALLOWED_EXTENSIONS = set(['txt', 'json'])

global_error = None

# Mongo client
mongo_uri = app.config['MONGODB_HOST']
mongo_user = app.config.get('MONGODB_USERNAME')
mongo_password = app.config.get('MONGODB_PASSWORD')


if mongo_user:
    client = MongoClient(mongo_uri, username=mongo_user, password=mongo_password)
else:
    client = MongoClient(mongo_uri)

# imageProcessingDB is the database containing lightsheet job information and parameters
# The current database is called "lightsheet" but should be renamed to better reflect all its functionality
imageProcessingDB = client.lightsheet

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

"""
 Url to return the favicon
"""
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')

"""
 Logout functionality
"""
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    auth_service = create_auth_service()
    auth_service.logout()
    return redirect(url_for('.index'))

"""
 View Function to configure jobs
"""
@app.route('/workflow', methods=['GET', 'POST'])
@login_required
def workflow():
    pipelineSteps = None
    jobName = None
    posted = "false"

    #Get HTML query values
    step_name = request.args.get('step')
    template_name = request.args.get('template')
    config_name = request.args.get('config_name')
    lightsheetDB_id = request.args.get('lightsheetDB_id')
    reparameterize = request.args.get('reparameterize')
    pInstance = PipelineInstance.objects.filter(name=config_name).first()

    if pInstance:  # Then load an uploaded config
        uploadedContent = json.loads(pInstance.content)
        configObj = buildConfigObject({'steps':uploadedContent['steps']})
        pipelineSteps, step_name, template_name = loadUploadedConfig(uploadedContent, configObj)
        if not (step_name or template_name):
            template_name = 'Deprecated Workflow'

    #Get the appropriate step or template name and build corresponding config objects
    deprecated = False
    stepOrTemplateName = ''
    if template_name:
        allTemplates =  list(imageProcessingDB.template.find({},{'name':1,'_id':0}))
        allTemplateNames = [template['name'] for template in allTemplates]
        stepOrTemplateName = "Template: " + template_name
        if template_name in allTemplateNames:
            configObj = buildConfigObject({'template':template_name})
        else:
            deprecated=True
            if not pInstance:
                configObj = buildConfigObject()
    elif step_name:
        stepOrTemplateName = "Step: " + step_name
        configObj = buildConfigObject({'step':step_name})

    if lightsheetDB_id: #Then a previous job has been loaded
        if lightsheetDB_id == 'favicon.ico':
            lightsheetDB_id = None
        else:
            pipelineSteps, loadStatus, jobName, username = loadPreexistingJob(imageProcessingDB, lightsheetDB_id, reparameterize, configObj)
            pipelineStepsWithConfig=[]
            if deprecated:
                for pipelineStepName in pipelineSteps:
                    pipelineStepsWithConfig.append([step for step in configObj['steps'] if step.name==pipelineStepName][0])
                configObj['steps'] = pipelineStepsWithConfig
            if reparameterize and current_user.username != username:
                #Then don't allow because not the same user as the user who submitted the job
                abort(404)

    if request.method == 'POST':
        posted = "true"
        submissionStatus = doThePost(request.url_root, request.json, reparameterize, imageProcessingDB,
                                    lightsheetDB_id,
                                    None,
                                    stepOrTemplateName)
        return submissionStatusReturner(submissionStatus)

    return render_template('index.html',
                           pipelineSteps=pipelineSteps,
                           config=configObj,
                           currentStep=step_name,
                           currentTemplate=template_name,
                           posted=posted,
                           jobName=jobName,
                           value_dependency = add_value_dependency_object(configObj),
                           dimension_dependency = add_dimension_dependency_object(configObj))

"""
 Root view function
"""
@app.route('/', methods=['GET'])
@login_required
def index():
    return redirect(url_for('workflow', template='AIC SimView Single Camera'))

"""
 View Function to the the status of jobs
"""
@app.route('/job_status', methods=['GET', 'POST'])
@login_required
def job_status():
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
        username = pausedJobInformation["username"]
        if current_user.username != username:
            #Then don't allow because not the same user as the user who submitted the job
            abort(404)
        # Make sure that we pop off all steps that have completed and been approved, ie, ones that are no longer in remaining
        pausedStates = [step['pause'] if ('pause' in step and step["name"] in pausedJobInformation["remainingStepNames"]) else 0 for step in pausedJobInformation["steps"]]
        pausedStepIndex = next((i for i, pausable in enumerate(pausedStates) if pausable), None)
        while pausedJobInformation["remainingStepNames"][0] != pausedJobInformation["steps"][pausedStepIndex]["name"]:
             pausedJobInformation["remainingStepNames"].pop(0)
        pausedJobInformation["remainingStepNames"].pop(0)  # Remove steps that have been completed/approved
        imageProcessingDB.jobs.update_one({"_id": ObjectId(imageProcessingDB_id)}, {"$set": pausedJobInformation})
        if pausedJobInformation["remainingStepNames"]: #only submit if not empty
            submissionStatus = submitToJACS(request.url_root, imageProcessingDB, imageProcessingDB_id, True)
        updateDBStatesAndTimes(imageProcessingDB)

    if imageProcessingDB_id is not None:
        jobType, stepOrTemplateName, childJobInfo, remainingStepNames = getJobInfoFromDB(imageProcessingDB, imageProcessingDB_id, "child")
        if not stepOrTemplateName:
            stepOrTemplateName = "Deprecated Workflow"
    # Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html',
                           parentJobInfo=reversed(parentJobInfo),  # so in chronolgical order
                           childJobInfo=childJobInfo,
                           lightsheetDB_id=imageProcessingDB_id,
                           stepOrTemplateName=stepOrTemplateName,
                           jobType=jobType,
                           posted=posted,
                           remainingStepNames=remainingStepNames)


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

"""
 View Function for loading a pipeline from a json file
"""
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


"""
 View Function for creating pipeline model records from a pipeline json file
"""
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

"""
 View Function for creating a configuration record in the database of an existing pipeline from a json file
"""
@app.route('/upload_config/<filename>', methods=['GET', 'POST'])
@login_required
def upload_config(filename=None):
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = createConfig(c)
        return redirect(url_for('workflow', config_name=result['name']))
        # return render_template('upload.html', content=c, filename=filename, message=result['message'], success=result['success'])
    message = []
    message.append('Error uploading the file {0}'.format(filename))
    ##return render_template('upload.html', filename=filename, message=message)

"""
 View Function for loading the configuration of an existing pipeline from a json file
"""
@app.route('/load_config', methods=['GET', 'POST'])
@login_required
def load_config(filename=None):
    if request.method == "GET":
        steps = Step.objects.all()
        empty = False
        if len(steps) == 0:
            empty = True
        return render_template(
            'load_config.html',
            empty=empty
        )

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
            return redirect(url_for('upload_config',
                                    filename=filename))
        else:
            # allowed_ext = print(', '.join(ALLOWED_EXTENSIONS[:-1]) + " or " + ALLOWED_EXTENSIONS[-1])
            allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
            message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
            return render_template('upload.html', message=message)
        return 'error'


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


@app.route('/download_settings/', methods=['GET', 'POST'])
@login_required
def download_settings():
    if request.method == 'POST':
        postedJson = request.json
        jobName = ''
        if 'jobName' in postedJson.keys():
            jobName = postedJson['jobName']
            del (postedJson['jobName'])
        reformattedData = reformatDataToPost(postedJson, False)
        reformattedData = {'name': jobName,
                           'steps': reformattedData[0],
                           }
        response = app.response_class(
            response=json.dumps(reformattedData),
            status=200,
            mimetype='application/json'
        )
        return response

@app.route('/hide_entries/', methods=['POST'])
@login_required
def hide_entries():
    ids_to_hide = request.json
    for i, id_to_hide in enumerate(ids_to_hide):
        ids_to_hide[i] = ObjectId(id_to_hide)
    output=imageProcessingDB.jobs.update_many({"username": current_user.username, "_id": {"$in": ids_to_hide}},{"$set":{"hideFromView":1}})
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


def createDependencyResults(dependencies, configObj):
    globalParameters = []
    nonGlobalParameters = []
    for step in configObj["steps"]:
        if "GLOBALPARAMETERS" in step.name.upper():
            globalParameters = [parameter.name for parameter in step.parameter]
        else:
            nonGlobalParameters=nonGlobalParameters+[parameter.name for parameter in step.parameter]

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

def submissionStatusReturner(submissionStatus):
    if submissionStatus=="success":
        return json.dumps({'status': submissionStatus}), 200, {'ContentType': 'application/json'}
    else:
        return json.dumps({'status': submissionStatus}), 404, {'ContentType': 'application/json'}

@app.route('/all_jobs', methods=['GET'])
@login_required
def all_jobs():
    return render_template('all_jobs.html')  # used by the job table

@app.route('/table_data', methods=['GET'])
@login_required
def table_data():
    showAllJobs = request.args.get('showAllJobs')=='True'
    updateDBStatesAndTimes(imageProcessingDB,showAllJobs)
    data = allJobsInJSON(imageProcessingDB,showAllJobs)
    output={}
    output['data'] = data
    response = app.response_class(
        response=json.dumps(output),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route('/copy_step', methods=['GET','POST'])
@login_required
def copy_step():
    if current_user.username in app.config.get('ADMINS'):
        originalStepName = request.args.get('from')
        newStepName = request.args.get('to')
        description = request.args.get('description')
        copyStepInDatabase(imageProcessingDB, originalStepName, newStepName, description)
        response = app.response_class(
            status=200,
            mimetype='application/json'
        )
    return response

@app.route('/delete_step_and_references/<stepName>', methods=['GET','POST'])
@login_required
def delete_step_and_references(stepName):
    if current_user.username in app.config.get('ADMINS'):
        if stepName:
            deleteStepAndReferencesFromDatabase(imageProcessingDB, stepName)
        response = app.response_class(
            status=200,
            mimetype='application/json'
        )
    return response

def add_value_dependency_object(configObj):
    dep = Dependency.objects.filter(dependency_type='V')
    result = []
    if dep is not None:
        result = createDependencyResults(dep, configObj)
    return result


def add_dimension_dependency_object(configObj):
    dep = Dependency.objects.filter(dependency_type='D')
    result = []
    if dep is not None:
        result = createDependencyResults(dep, configObj)
    return result

