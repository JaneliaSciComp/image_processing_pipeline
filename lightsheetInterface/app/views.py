# Contains routes and functions to pass content to the template layer
import json, os

from flask import render_template, request, jsonify, abort, send_from_directory, flash
from flask import send_from_directory, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from app import app
from app.authservice import create_auth_service
from app.forms import LoginForm
from app.utils import *
from app.jobs_io import reformat_data_to_post, submit_the_job_to_db_and_jacs, load_preexisting_job, load_uploaded_config
from app.models import Dependency
from bson.objectid import ObjectId

# This file contains all the view components necessary for routing and loading the correct webpages


ALLOWED_EXTENSIONS = {'txt', 'json'}

# Mongo client
MONGO_URI = app.config['MONGODB_HOST']
MONGO_DB = app.config['MONGODB_DB']
MONGO_USER = app.config.get('MONGODB_USERNAME')
MONGO_PASSWORD = app.config.get('MONGODB_PASSWORD')

if MONGO_USER:
    print(f'Connect to {MONGO_URI}:{MONGO_DB}')
    CLIENT = MongoClient(MONGO_URI, username=MONGO_USER, password=MONGO_PASSWORD)
else:
    CLIENT = MongoClient(MONGO_URI)

# imageProcessingDB is the database containing lightsheet job information and parameters
# The current database is called "lightsheet" but should be renamed to better reflect all its functionality
IMAGE_PROCESSING_DB = CLIENT[MONGO_DB]


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
    pipeline_steps = None
    job_name = None

    # Get HTML query values
    step_name = request.args.get('step')
    template_name = request.args.get('template')
    configuration_name = request.args.get('config_name')
    image_processing_db_id = request.args.get('lightsheetDB_id')
    reparameterize = request.args.get('reparameterize')
    pipeline_instance = PipelineInstance.objects.filter(name=configuration_name).first()

    if pipeline_instance:  # Then load an uploaded config
        uploaded_content = json.loads(pipeline_instance.content)
        configuration_object = build_configuration_object({'steps': uploaded_content['steps']})
        pipeline_steps, step_name, template_name = load_uploaded_config(uploaded_content, configuration_object)
        if not (step_name or template_name):
            template_name = 'Deprecated Workflow'

    # Get the appropriate step or template name and build corresponding config objects
    deprecated = False
    step_or_template_name = ''
    if template_name:
        all_templates = list(IMAGE_PROCESSING_DB.template.find({}, {'name': 1, '_id': 0}))
        all_template_names = [template['name'] for template in all_templates]
        step_or_template_name = "Template: " + template_name
        if template_name in all_template_names:
            configuration_object = build_configuration_object({'template': template_name})
        else:
            deprecated = True
            if not pipeline_instance:
                configuration_object = build_configuration_object()
    elif step_name:
        step_or_template_name = "Step: " + step_name
        configuration_object = build_configuration_object({'step': step_name})

    if image_processing_db_id:  # Then a previous job has been loaded
        if image_processing_db_id == 'favicon.ico':
            image_processing_db_id = None
        else:
            pipeline_steps, load_status, job_name, username = load_preexisting_job(IMAGE_PROCESSING_DB, image_processing_db_id, reparameterize, configuration_object)
            pipelineStepsWithConfig = []
            if deprecated:
                for pipelineStepName in pipeline_steps:
                    pipelineStepsWithConfig.append([step for step in configuration_object['steps'] if step.name == pipelineStepName][0])
                configuration_object['steps'] = pipelineStepsWithConfig
            if reparameterize and current_user.username != username:
                # Then don't allow because not the same user as the user who submitted the job
                abort(404)

    if request.method == 'POST':
        submission_status = submit_the_job_to_db_and_jacs(request.url_root, request.json, reparameterize, IMAGE_PROCESSING_DB,
                                                          image_processing_db_id,
                                                          None,
                                                          step_or_template_name)
        return submission_status_returner(submission_status)

    return render_template('index.html',
                           pipelineSteps=pipeline_steps,
                           config=configuration_object,
                           currentStep=step_name,
                           currentTemplate=template_name,
                           jobName=job_name,
                           global_dependencies=add_global_dependency_object(configuration_object))


"""
 Root view function
"""
@app.route('/', methods=['GET'])
@login_required
def index():
    all_workflows = list(IMAGE_PROCESSING_DB.template.find({}, {'name': 1}))
    workflow_names = [workflow['name'] for workflow in all_workflows]
    if len(all_workflows)==0:
        return redirect(url_for('workflow', template='NO WORKFLOWS CREATED YET'))
    elif 'AIC SimView Single Camera' in workflow_names:
        return redirect(url_for('workflow', template='AIC SimView Single Camera'))
    else:
        return redirect(url_for('workflow', template=workflow_names[0]))





"""
 View Function to the the status of jobs and for resuming jobs
"""
@app.route('/job_status', methods=['GET', 'POST'])
@login_required
def job_status():
    image_processing_db_id = request.args.get('lightsheetDB_id')
    # Mongo client
    update_db_states_and_times(IMAGE_PROCESSING_DB)
    parent_job_info = get_job_information(IMAGE_PROCESSING_DB, image_processing_db_id, "parent")
    child_job_info = []
    job_type = []
    step_or_template_name = []
    posted = "false"
    remaining_step_names = None

    if request.method == 'POST':
        # Find pause that is in remaining steps
        posted = "true"
        paused_job_information = list(IMAGE_PROCESSING_DB.jobs.find({"_id": ObjectId(image_processing_db_id)}))
        paused_job_information = paused_job_information[0]
        username = paused_job_information["username"]
        if current_user.username != username:
            # Then don't allow because not the same user as the user who submitted the job
            abort(404)
        # Make sure that we pop off all steps that have completed and been approved, ie, ones that are no longer in remaining
        paused_states = [step['pause'] if ('pause' in step and step["name"] in paused_job_information["remainingStepNames"]) else 0 for step in paused_job_information["steps"]]
        paused_step_index = next((i for i, pausable in enumerate(paused_states) if pausable), None)
        while paused_job_information["remainingStepNames"][0] != paused_job_information["steps"][paused_step_index]["name"]:
            paused_job_information["remainingStepNames"].pop(0)
        paused_job_information["remainingStepNames"].pop(0)  # Remove steps that have been completed/approved
        IMAGE_PROCESSING_DB.jobs.update_one({"_id": ObjectId(image_processing_db_id)}, {"$set": paused_job_information})
        if paused_job_information["remainingStepNames"]:  # only submit if not empty
            submit_to_jacs(request.url_root, IMAGE_PROCESSING_DB, image_processing_db_id, True)
        update_db_states_and_times(IMAGE_PROCESSING_DB)

    if image_processing_db_id is not None:
        job_type, step_or_template_name, child_job_info, remaining_step_names = get_job_information(IMAGE_PROCESSING_DB, image_processing_db_id, "child")
        if not step_or_template_name:
            step_or_template_name = "Deprecated Workflow"

    # Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html',
                           parentJobInfo=reversed(parent_job_info),  # so in chronolgical order
                           childJobInfo=child_job_info,
                           lightsheetDB_id=image_processing_db_id,
                           stepOrTemplateName=step_or_template_name,
                           jobType=job_type,
                           posted=posted,
                           remainingStepNames=remaining_step_names)


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
            return redirect(url_for('uploaded_file', filename=filename))
        else:
            allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
            message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
            return render_template('upload.html', message=message)


"""
 View Function for creating pipeline model records from a pipeline json file
"""
@app.route('/upload/<filename>', methods=['GET', 'POST'])
@login_required
def uploaded_file(filename=None):
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = create_db_entries(c)
        return render_template('upload.html', content=c, filename=filename, message=result['message'],
                               success=result['success'])
    message = []
    message.append('Error uploading the file {0}'.format(filename))

    return render_template('upload.html', filename=filename, message=message)


"""
 View Function for creating a configuration record in the database of an existing pipeline from a json file
"""
@app.route('/load_config/<filename>', methods=['GET', 'POST'])
@login_required
def load_config(filename=None):
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as file:
        c = json.loads(file.read())
        result = create_config(c)
        return redirect(url_for('workflow', config_name=result['name']))
        #return render_template('upload_config.html', content=c, filename=filename, message=result['message'], success=result['success'])
    message = []
    message.append('Error uploading the file {0}'.format(filename))
    #return render_template('upload_config.html', filename=filename, message=message)


"""
 View Function for loading the configuration of an existing pipeline from a json file
"""
@app.route('/upload_config', methods=['GET', 'POST'])
@login_required
def upload_config():
    if request.method == "GET":
        steps = Step.objects.all()
        empty = False
        if len(steps) == 0:
            empty = True
        return render_template(
            'upload_config.html',
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
            return redirect(url_for('load_config',filename=filename))
        else:
            allowed_ext = (', '.join(ALLOWED_EXTENSIONS))
            message = 'Please make sure, your file extension is one of the following: ' + allowed_ext
            return render_template('upload_config.html', message=message)


@app.route('/config/<image_processing_db_id>', methods=['GET'])
def config(image_processing_db_id):
    global_parameter = request.args.get('globalParameter')
    step_name = request.args.get('stepName')
    output = get_configurations_from_db(IMAGE_PROCESSING_DB, image_processing_db_id, global_parameter, step_name)
    if output == 404:
        abort(404)
    else:
        return jsonify(output)


@app.route('/download_settings/', methods=['GET', 'POST'])
@login_required
def download_settings():
    if request.method == 'POST':
        posted_json = request.json
        job_name = ''
        if 'jobName' in posted_json.keys():
            job_name = posted_json['jobName']
            del (posted_json['jobName'])
        reformatted_data = reformat_data_to_post(posted_json, False)
        reformatted_data = {'name': job_name,
                           'steps': reformatted_data[0],
                           }
        response = app.response_class(
            response=json.dumps(reformatted_data),
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
    IMAGE_PROCESSING_DB.jobs.update_many({"username": current_user.username, "_id": {"$in": ids_to_hide}}, {"$set": {"hideFromView": 1}})
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


def create_dependency_results(dependencies, configuration_object):
    global_parameters = []
    non_global_parameters = []
    for step in configuration_object["steps"]:
        if "GLOBALPARAMETERS" in step.name.upper():
            global_parameters = [parameter.name for parameter in step.parameter]
        else:
            non_global_parameters = non_global_parameters + [parameter.name for parameter in step.parameter]

    result = []
    for d in dependencies:
        input_field_name = d.inputField.name
        output_field_name = d.outputField.name
        if input_field_name in global_parameters and output_field_name in non_global_parameters:
            # #     # need to check here, if simple value transfer (for string or float values) or if it's a nested field
            obj = {}
            obj['input'] = d.inputField.name if d.inputField and d.inputField.name is not None else ''
            obj['output'] = d.outputField.name if d.outputField and d.outputField.name is not None else ''
            obj['pattern'] = d.pattern if d.pattern is not None else ''
            obj['formatting'] = d.inputField.formatting if d.inputField.formatting is not None else ''
            obj['step'] = output_field_name.split("_")[-1]
            result.append(obj)
    return result


def submission_status_returner(submission_status):
    if submission_status == "success":
        return json.dumps({'status': submission_status}), 200, {'ContentType': 'application/json'}
    else:
        return json.dumps({'status': submission_status}), 404, {'ContentType': 'application/json'}


@app.route('/all_jobs', methods=['GET'])
@login_required
def all_jobs():
    return render_template('all_jobs.html')  # used by the job table


@app.route('/table_data', methods=['GET'])
@login_required
def table_data():
    show_all_jobs = request.args.get('showAllJobs') == 'True'
    update_db_states_and_times(IMAGE_PROCESSING_DB, show_all_jobs)
    data = all_jobs_in_json(IMAGE_PROCESSING_DB, show_all_jobs)
    output = {}
    output['data'] = data
    response = app.response_class(
        response=json.dumps(output),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/copy_step', methods=['GET', 'POST'])
@login_required
def copy_step():
    if current_user.username in app.config.get('ADMINS'):
        original_step_name = request.args.get('from')
        new_step_name = request.args.get('to')
        description = request.args.get('description')
        copy_step_in_database(IMAGE_PROCESSING_DB, original_step_name, new_step_name, description)
        response = app.response_class(
            status=200,
            mimetype='application/json'
        )
    return response


@app.route('/delete_step_and_references/<step_name>', methods=['GET', 'POST'])
@login_required
def delete_step_and_references(step_name):
    if current_user.username in app.config.get('ADMINS'):
        if step_name:
            delete_step_and_references_from_database(IMAGE_PROCESSING_DB, step_name)
        response = app.response_class(
            status=200,
            mimetype='application/json'
        )
    return response


def add_global_dependency_object(configObj):
    dep = Dependency.objects.filter()
    result = []
    if dep is not None:
        result = create_dependency_results(dep, configObj)
    return result
