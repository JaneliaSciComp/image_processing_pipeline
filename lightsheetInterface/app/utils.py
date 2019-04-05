import datetime, json, requests, operator, time
from flask import url_for
from flask_login import current_user
from mongoengine import ValidationError, NotUniqueError
from datetime import datetime
from pytz import timezone
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
from app import app
from app.models import AppConfig, Step, Parameter, Template, PipelineInstance
from collections import OrderedDict
from itertools import repeat

# JACS server
JACS_HOST = app.config.get('JACS_HOST')

# Timezone for timings
EASTERN_TIMEZONE = timezone('US/Eastern')
UTC_TIMEZONE = timezone('UTC')


# collect the information about existing job used by the job_status page
def get_job_information(image_processing_db, _id, parent_or_child):
    _id = ObjectId(_id)
    job_information_from_db = get_job_information_from_db(image_processing_db, _id, parent_or_child)
    return add_fields_to_job_information_from_db(parent_or_child, job_information_from_db, _id)


def get_job_information_from_db(image_processing_db, _id, parent_or_child):
    if parent_or_child == "parent":
        job_information_from_db = list(image_processing_db.jobs.find({"username": current_user.username, "hideFromView": {"$ne": 1}}, {"configAddress": 1, "state": 1, "jobName": 1, "remainingStepNames": 1,
                                                                                                                                "creationDate": 1, "jacs_id": 1, "steps.name": 1,
                                                                                                                                "steps.state": 1}))
    else:
        job_information_from_db = list(image_processing_db.jobs.find({"username": current_user.username, "_id": _id},
                                                              {"remainingStepNames": 1, "stepOrTemplateName": 1, "steps.name": 1, "steps.state": 1,
                                                               "steps.creationTime": 1, "steps.endTime": 1,
                                                               "steps.elapsedTime": 1, "steps.logAndErrorPath": 1,
                                                               "steps.pause": 1, "steps._id": 1}))
        job_information_from_db = job_information_from_db[0]

    return job_information_from_db


def add_fields_to_job_information_from_db(parent_or_child, job_information_from_db, _id):
    all_steps = Step.objects.all()
    if parent_or_child == "parent":
        for current_job_info in job_information_from_db:
            selected_step_names = []
            for step in current_job_info["steps"]:
                step_template = next((step_template for step_template in all_steps if step_template.name == step["name"]), None)
                if step_template == None or step_template.submit:  # None implies a deprecated name
                    selected_step_names.append(step["name"])
            current_job_info.update({'selectedStepNames': ",".join(selected_step_names)})
            current_job_info.update({"selected": ""})
            if current_job_info["_id"] == _id:
                current_job_info.update({"selected": "selected"})
        return job_information_from_db
    elif parent_or_child == "child":
        child_job_info = []
        remaining_step_names = job_information_from_db["remainingStepNames"]
        for step in job_information_from_db["steps"]:
            step_template = next((stepTemplate for stepTemplate in all_steps if stepTemplate.name == step["name"]), None)
            if step_template == None or step_template.submit:  # None implies a deprecated name
                child_job_info.append(step)
        if 'stepOrTemplateName' in job_information_from_db and job_information_from_db['stepOrTemplateName'] is not None:
            step_or_template_name = job_information_from_db["stepOrTemplateName"]
            step_or_template_name_path = step_or_template_name_url_maker(step_or_template_name)
        else:
            step_or_template_name = ''
            step_or_template_name_path = ''
        return step_or_template_name, step_or_template_name_path, child_job_info, remaining_step_names
    else:
        return 404


# get job information used by jquery datatable
def all_jobs_in_json(image_processing_db, show_all_jobs=False):
    if show_all_jobs:
        parent_job_info = image_processing_db.jobs.find({"username": {"$exists": "true"}, "hideFromView": {"$ne": 1}}, {"_id": 1, "username": 1, "jobName": 1, "remainingStepNames": 1, "submissionAddress": 1, "creationDate": 1,
                                                                                                                        "state": 1, "jacs_id": 1, "stepOrTemplateName": 1,
                                                                                                                        "steps.state": 1, "steps.name": 1, "steps.pause": 1})
    else:
        parent_job_info = image_processing_db.jobs.find({"username": current_user.username, "hideFromView": {"$ne": 1}}, {"_id": 1, "jobName": 1, "remainingStepNames": 1, "submissionAddress": 1, "creationDate": 1,
                                                                                                                          "state": 1, "jacs_id": 1, "stepOrTemplateName": 1,
                                                                                                                          "steps.state": 1, "steps.name": 1, "steps.pause": 1})
    all_steps = Step.objects.all()
    list_to_return = list(map(map_jobs_to_dictionary, parent_job_info, repeat(all_steps)))
    return list_to_return


# build result object of existing job information
def map_jobs_to_dictionary(parent_job_information, all_steps):
    job_dictionary = build_job_dictionary_with_overall_information(parent_job_information)
    return add_step_information_to_job_dictionary(parent_job_information, job_dictionary, all_steps)


def build_job_dictionary_with_overall_information(parent_job_information):
    job_dictionary = {}
    all_parameters = ['username', 'jobName', 'username', 'creationDate', 'state', 'jacs_id', '_id', 'submissionAddress', 'stepOrTemplateName']
    for current_parameter in all_parameters:
        if current_parameter in parent_job_information:
            if current_parameter == '_id':
                job_dictionary['id'] = str(parent_job_information[current_parameter]) if str(parent_job_information[current_parameter]) is not None else ''
            elif current_parameter == 'stepOrTemplateName':
                if parent_job_information['stepOrTemplateName'] is not None:
                    job_dictionary['stepOrTemplateName'] = step_or_template_name_url_maker(parent_job_information['stepOrTemplateName'])
                    job_dictionary["jobType"] = parent_job_information['stepOrTemplateName']
                else:
                    job_dictionary['stepOrTemplateName'] = ''
                    job_dictionary["jobType"] = ''
            else:
                job_dictionary[current_parameter] = parent_job_information[current_parameter] if parent_job_information[current_parameter] is not None else ''
        elif current_parameter == 'submissionAddress':
            job_dictionary['submissionAddress'] = ''
        elif current_parameter == 'stepOrTemplateName':
            job_dictionary['stepOrTemplateName'] = ''
            job_dictionary["jobType"] = ''
    return job_dictionary


def add_step_information_to_job_dictionary(parent_job_information, job_dictionary, all_steps):
    job_dictionary['selectedSteps'] = {'names': [], 'states': [], 'submissionAddress': ''}
    for i, step in enumerate(parent_job_information["steps"]):
        step_template = next((step_template for step_template in all_steps if step_template.name == step["name"]), None)
        if step_template == None or step_template.submit:  # None implies a deprecated name
            job_dictionary['selectedSteps']['submissionAddress'] = job_dictionary['submissionAddress']
            job_dictionary['selectedSteps']['names'].append(step["name"])
            job_dictionary['selectedSteps']['states'].append(step["state"])
            if step['state'] not in ["CREATED", "SUCCESSFUL", "RUNNING", "NOT YET QUEUED", "QUEUED", "DISPATCHED"]:
                if step["name"] in parent_job_information['remainingStepNames']:
                    job_dictionary['selectedSteps']['states'].append('RESET')
            elif "pause" in step and step['pause'] and step['state'] == "SUCCESSFUL":
                if step["name"] in parent_job_information['remainingStepNames']:
                    job_dictionary['selectedSteps']['states'].append('RESUME,RESET')
    job_dictionary['selectedSteps']['names'] = ",".join(job_dictionary['selectedSteps']['names'])
    job_dictionary['selectedSteps']['states'] = ",".join(job_dictionary['selectedSteps']['states'])
    return job_dictionary


# build object with meta information about parameters from the admin interface
def get_parameters(parameters):
    for parameter in parameters:
        if parameter.number1 is not None:
            parameter.type = 'Integer'
            if parameter.number2 is None:
                parameter.count = '1'
            elif parameter.number3 is None:
                parameter.count = '2'
            elif parameter.number4 is None:
                parameter.count = '3'
            elif parameter.number5 is None:
                parameter.count = '4'
            elif parameter.number6 is None:
                parameter.count = '5'
            else:
                parameter.count = '6'
        elif parameter.float1:
            parameter.type = 'Float'
            parameter.count = '1'
        elif parameter.text1:
            parameter.type = 'Text'
            if not parameter.text2:
                parameter.count = '1'
            elif not parameter.text3:
                parameter.count = '2'
            elif not parameter.text4:
                parameter.count = '3'
            elif not parameter.text5:
                parameter.count = '4'
            else:
                parameter.count = '5'

    return parameters


# build object with information about steps and parameters about admin interface
def build_configuration_object(step_or_template_dictionary=None):
    try:
        current_steps = []
        # Check if we are loading a default step/template in which case we just need to load the corresponding information
        # Else, we need to load all possible settings since we are loading a deprecated step/template name which may contain steps in order we don't expect
        if step_or_template_dictionary:
            if 'step' in step_or_template_dictionary:
                step_name = step_or_template_dictionary['step']
                current_steps = Step.objects.all().filter(name=step_name)[0]
                current_steps['parameter'] = get_parameters(current_steps.parameter)
                current_steps = [current_steps]
            elif 'template' in step_or_template_dictionary:
                template_name = step_or_template_dictionary['template']
                template = Template.objects.all().filter(name=template_name)
                current_steps = sorted(template[0].steps, key=operator.attrgetter('order'))
                for step in current_steps:
                    step['parameter'] = get_parameters(step['parameter'])
            elif 'steps' in step_or_template_dictionary:
                for temp_step in step_or_template_dictionary['steps']:
                    if 'name' in temp_step:
                        step_name = temp_step['name']
                    else:
                        step_name = temp_step
                    step = Step.objects.all().filter(name=step_name)[0]
                    step['parameter'] = get_parameters(step['parameter'])
                    current_steps.append(step)
        else:
            all_steps = Step.objects.all()
            for step in all_steps:
                step['parameter'] = get_parameters(step['parameter'])
                current_steps.append(step)

        config = {
            'steps': current_steps,
            'stepNames': get_step_names(),
            'templateNames': get_template_names()
        }

    except ServerSelectionTimeoutError:
        return 404
    return config


def get_step_names():
    return Step.objects.all().values_list('name')


def get_template_names():
    return Template.objects.all().order_by('order').values_list('name')


# Header for post request
def get_headers(for_query=False):
    if for_query:
        return {
            'content-type': 'application/json',
            'USERNAME': current_user.username if current_user.is_authenticated else ""
        }
    else:
        # for now runasuser is the same as the authenticated user
        # but maybe in the future the feature will be supported
        return {
            'content-type': 'application/json',
            'USERNAME': current_user.username if current_user.is_authenticated else "",
            # 'RUNASUSER': current_user.username if current_user.is_authenticated else ""
        }


# get step information about existing jobs from db
def get_job_step_data(_id, image_processing_db):
    result = get_configurations_from_db(_id, image_processing_db)
    if (result is not None) and result != 404 and len(result) > 0 and 'steps' in result[0]:
        return result[0]['steps']
    return None


# get the job parameter information from db
def get_configurations_from_db(image_processing_db_id, image_processing_db, global_parameter=None, step_name=None):
    if global_parameter:
        output = list(image_processing_db.jobs.find({'_id': ObjectId(image_processing_db_id)}, {'_id': 0, global_parameter: 1}))[0]
        if not output:
            output = {global_parameter: ""}
    else:
        if step_name:
            output = list(image_processing_db.jobs.find({'_id': ObjectId(image_processing_db_id), 'steps.name': step_name}, {'_id': 0, "steps.$": 1}))
            if output:
                output = output[0]["steps"][0]["parameters"]
        else:
            output = list(image_processing_db.jobs.find({'_id': ObjectId(image_processing_db_id)}, {'_id': 0, 'steps': 1}))

    if output:
        return output
    return 404


# get latest status information about jobs from db
def update_db_states_and_times(image_processing_db, show_all_jobs=False):
    if current_user.is_authenticated:
        if show_all_jobs:
            relevant_job_information_from_db = list(image_processing_db.jobs.find({"username": {"$exists": "true"}, "state": {"$in": ["NOT YET QUEUED", "RUNNING", "CREATED", "QUEUED", "DISPATCHED"]}}))
        else:
            relevant_job_information_from_db = list(image_processing_db.jobs.find({"username": current_user.username, "state": {"$in": ["NOT YET QUEUED", "RUNNING", "CREATED", "QUEUED", "DISPATCHED"]}}))

        find_and_set_dictionaries_for_db_update = build_find_and_set_dictionaries_for_db_update(relevant_job_information_from_db)

        for current_find_and_set_dictionaries in find_and_set_dictionaries_for_db_update:
            image_processing_db.jobs.update_one(current_find_and_set_dictionaries['find'], current_find_and_set_dictionaries['set'])


def build_find_and_set_dictionaries_for_db_update(relevant_job_information_from_db):
    find_and_set_dictionaries = []
    for parent_job_info_from_db in relevant_job_information_from_db:
        if 'jacs_id' in parent_job_info_from_db:  # TODO handle case, when jacs_id is missing
            if isinstance(parent_job_info_from_db["jacs_id"], list):
                jacs_ids = parent_job_info_from_db["jacs_id"]
            else:
                jacs_ids = [parent_job_info_from_db["jacs_id"]]

            for jacs_id in jacs_ids:
                parent_job_info_from_jacs = get_job_info_from_jacs({'service-id': jacs_id})
                if parent_job_info_from_jacs and len(parent_job_info_from_jacs["resultList"]) > 0:
                    parent_job_info_from_jacs = parent_job_info_from_jacs["resultList"][0]
                    parent_dictionary = { 'find': {"_id": parent_job_info_from_db["_id"]}, 'set': {"$set": {"state": parent_job_info_from_jacs["state"]}} }
                    find_and_set_dictionaries.append(parent_dictionary)
                    all_child_job_info_from_jacs = get_job_info_from_jacs({'parent-id': jacs_id})
                    all_child_job_info_from_jacs = all_child_job_info_from_jacs["resultList"]
                    if all_child_job_info_from_jacs:
                        for current_child_job_info_from_db in parent_job_info_from_db["steps"]:
                            current_child_job_info_from_jacs = next((step for step in all_child_job_info_from_jacs if (current_child_job_info_from_db["name"] in step["description"])), None)
                            if current_child_job_info_from_db["state"] == "NOT YET QUEUED" and jacs_id != jacs_ids[-1]:  # NOT YET QUEUED jobs were just submitted so only want to check based on currently running job
                                current_child_job_info_from_jacs = {}
                            if current_child_job_info_from_jacs:
                                creation_time = convert_jacs_time(current_child_job_info_from_jacs["processStartTime"])
                                find_dictionary = {"_id": parent_job_info_from_db["_id"], "steps.name": current_child_job_info_from_db["name"]}
                                set_dictionary = {"steps.$.state": current_child_job_info_from_jacs["state"],
                                                  "steps.$.creationTime": creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                                                  "steps.$.elapsedTime": str(datetime.now(EASTERN_TIMEZONE).replace(microsecond=0) - creation_time),
                                                  "steps.$._id": (current_child_job_info_from_jacs["_id"] if "_id" in current_child_job_info_from_jacs else current_child_job_info_from_jacs["id"])}

                                if current_child_job_info_from_jacs["state"] in ['CANCELED', 'TIMEOUT', 'ERROR', 'SUCCESSFUL']:  # Add endTime and elapsedTime
                                    end_time = convert_jacs_time(current_child_job_info_from_jacs["modificationDate"])
                                    set_dictionary = {**set_dictionary, **{"steps.$.endTime": end_time.strftime("%Y-%m-%d %H:%M:%S"), "steps.$.elapsedTime": str(end_time - creation_time)}}
                                step_dictionary={'find': find_dictionary, 'set': {"$set": set_dictionary } }
                                find_and_set_dictionaries.append(step_dictionary)
    return find_and_set_dictionaries

def get_job_info_from_jacs(request_params_dictionary):
    request_output_jsonified = requests.get(JACS_HOST + ':9000/api/rest-v2/services/',
                                            params=request_params_dictionary,
                                            headers=get_headers(True)).json()
    return request_output_jsonified


def convert_jacs_time(t):
    t = datetime.strptime(t[:-9], '%Y-%m-%dT%H:%M:%S')
    t = UTC_TIMEZONE.localize(t).astimezone(EASTERN_TIMEZONE)
    return t


def create_db_entries(content):
    message = []
    success = False
    if type(content) is list:
        content = content[0]
    keys = content.keys()
    for key in keys:
        obj = content[key]
        if key == 'parameters':
            for o in obj:
                p = Parameter()
                p.name = o
                p.displayName = o
                value = obj[o]
                if type(value) is dict:
                    if 'start' in value and 'end' in value and 'every' in value:
                        p.frequency = 'F'
                        p.formatting = 'R'
                        p.number1 = value['start']
                        p.number2 = value['end']
                        p.number3 = value['every']
                else:
                    p.frequency = 'F'
                    if type(value) == str:
                        p.text1 = value
                    elif type(value) == float:
                        p.number1 = value
                    elif type(value) == list:
                        # TODO: distinguish in between the different types
                        continue
                try:
                    p.save()
                except OSError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except ValidationError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except NotUniqueError:
                    message.append('Parameter with the name "{0}" has already been added: '.format(p['name']))
                    pass
        elif key == 'steps':
            for o in obj:
                s = Step()
                if 'name' in o:
                    s['name'] = o['name']
                if 'order' in o:
                    s['order'] = o['order']
                if 'description' in o:
                    s['description'] = o['description']
                if 'parameters' in o:
                    # Query for steps and associate them with template
                    for param in o['parameters']:
                        parameter_object = Parameter.objects.filter(name=param).first()
                        if parameter_object:
                            s['parameter'].append(parameter_object.pk)
                try:
                    s.save()
                except ValidationError as e:
                    message.append('Error creating the parameter: ' + str(e))
                    pass
                except NotUniqueError:
                    message.append('Step with the name "{0}" has already been added.'.format(o['name']))
                    pass
        elif key == 'template':
            for o in obj:
                t = Template()
                if 'name' in o:
                    t.name = o['name']
                if 'steps' in o:
                    # Query for steps and associate them with template
                    for step in o['steps']:
                        step_object = Step.objects.filter(name=step).first()
                        if step_object:
                            t['steps'].append(step_object)
                        else:
                            print('No step object found')
                try:
                    t.save()
                except ValidationError as e:
                    message.append('Error creating the template: ' + str(e))
                    pass
                except NotUniqueError:
                    message.append('Template with the name "{0}" has already been added.'.format(o['name']))
                    pass
                except:
                    message.append('There was an error creating a template')
                    pass

    if len(message) == 0:
        success = True
        message.append('File has been uploaded successfully.')

    result = {'message': message, 'success': success}
    return result


def create_config(content):
    pipeline_instance = PipelineInstance()
    json_object = json.dumps(OrderedDict(content))
    pipeline_instance.content = json_object

    if 'name' in content:
        pipeline_instance.description = content['name']
    pipeline_instance.save()

    # Create new database objects configuration and configuration instances
    result = {'message': [], 'success': True, 'name': pipeline_instance.name}
    return result


def submit_to_jacs(config_server_url, image_processing_db, job_id, continue_or_reparameterize):
    job_id = ObjectId(job_id)
    config_address = config_server_url + "config/{}".format(job_id)
    post_body, post_url = build_post_body_for_jacs(image_processing_db, job_id)

    # Do the submission to JACS
    try:
        request_output = requests.post(post_url,
                                       headers=get_headers(),
                                       data=json.dumps(post_body))
        request_output_jsonified = request_output.json()
        creation_date = job_id.generation_time
        creation_date = str(creation_date.replace(tzinfo=UTC_TIMEZONE).astimezone(EASTERN_TIMEZONE))
        jacs_id = request_output_jsonified['_id'] if '_id' in request_output_jsonified else request_output_jsonified['id']

        if continue_or_reparameterize:
            image_processing_db.jobs.update_one({"_id": job_id}, {"$set": {"state": "NOT YET QUEUED"}, "$push": {
                "jacsStatusAddress": JACS_HOST + '8080/job/' + jacs_id,
                "jacs_id": jacs_id}})
        else:
            image_processing_db.jobs.update_one({"_id": job_id}, {
                "$set": {"jacs_id": [jacs_id], "configAddress": config_address,
                         "creationDate": creation_date[:-6]}})

        update_db_states_and_times(image_processing_db)
        submission_status = "success"
    except requests.exceptions.RequestException:
        print('Exception occured')
        submission_status = requests
        if not continue_or_reparameterize:
            image_processing_db.jobs.remove({"_id": job_id})
    return submission_status


def build_post_body_for_jacs(image_processing_db, job_id):
    job_info_from_database = list(image_processing_db.jobs.find({"_id": job_id}))
    job_info_from_database = job_info_from_database[0]
    remaining_steps = []
    remaining_step_names = job_info_from_database["remainingStepNames"]
    pause_state = False
    current_step_index = 0
    while not pause_state and current_step_index < len(job_info_from_database["steps"]):
        step = job_info_from_database["steps"][current_step_index]
        if step["name"] in remaining_step_names:
            remaining_steps.append(step)
            if "pause" in step:
                pause_state = step["pause"]
        current_step_index = current_step_index + 1

    post_body = {"ownerKey": "user:" + current_user.username if current_user.is_authenticated else "",
                 "resources": {"gridAccountId": current_user.username}}
    pipeline_services = []
    for step in remaining_steps:
        if step["type"] == "LightSheet":
            step_post_body = step
            step_post_body["stepResources"] = {"softGridJobDurationInSeconds": "1200"}
        elif step["type"] == "Sparks":
            step_post_body = {
                "stepName": step["name"],
                "serviceName": "sparkAppProcessor",
                "serviceProcessingLocation": 'LSF_JAVA',
                "serviceArgs": [
                    "-appLocation", step["codeLocation"],
                    "-appEntryPoint", step["entryPointForSpark"],
                    "-appArgs", step["parameters"]["-appArgs"]
                ]}
            if "-numNodes" in step["parameters"]:
                step_post_body["serviceResources"] = {"sparkNumNodes": str(int(step["parameters"]["-numNodes"]))}
        else:  # Singularity
            step_post_body = {
                "stepName": step["name"],
                "serviceName": "runSingularityContainer",
                "serviceProcessingLocation": 'LSF_JAVA',
                "serviceArgs": [
                    "-containerLocation", step["codeLocation"],
                    "-singularityRuntime", "/usr/bin/singularity",
                    "-bindPaths", step["bindPaths"],
                    "-appArgs", step["parameters"]["-appArgs"]
                ]
            }
            if "numberOfProcessors" in step["parameters"]:
                step_post_body["serviceResources"] = {"nSlots": str(int(step["parameters"]["numberOfProcessors"]))}
            for argName in ["-expandDir", "-expandPattern", "-expandedArgFlag", "-expandedArgList", "-expandDepth"]:
                if argName in step["parameters"]:
                    step_post_body["serviceArgs"].extend((argName, step["parameters"][argName]))

        pipeline_services.append(step_post_body)
    if remaining_steps[0]['type'] == "LightSheet":
        post_url = JACS_HOST + ':9000/api/rest-v2/async-services/lightsheetPipeline'
        post_body['processingLocation'] = 'LSF_JAVA'
        post_body["dictionaryArgs"] = {"pipelineConfig": {"steps": pipeline_services}}
    else:
        post_url = JACS_HOST + ':9000/api/rest-v2/async-services/pipeline'
        post_body["dictionaryArgs"] = {"pipelineConfig": {"pipelineServices": pipeline_services}}

    return post_body, post_url


def step_or_template_name_url_maker(step_or_template_name):
    if step_or_template_name.find("Step: ", 0, 6) != -1:
        step_or_template_name = url_for('workflow', step=step_or_template_name[6:])
    else:
        step_or_template_name = url_for('workflow', template=step_or_template_name[10:])
    return step_or_template_name

## THE REMAINNIG FUNCTIONS ARE CURRENTLY ONLY FOR QUICKLY COPYING SETPS AND DELETING PARAMETERS FOR ADMIN USE. THERE IS NO FORMAL UI WAY TO DO IT YET, JUST VIA HTML REQUESTS ##
def copy_step_in_database(image_processing_db, original_step_name, new_step_name, new_step_description=None):
    original_step = list(image_processing_db.step.find({"name": original_step_name}, {'_id': 0}))
    if original_step:
        original_step = original_step[0]
        new_step = original_step
        new_step["name"] = new_step_name
        original_parameters = original_step['parameter']
        new_parameter_ids = copy_parameter_in_database(image_processing_db, original_parameters, original_step_name, new_step_name)
        if new_step_description:
            new_step['Description'] = new_step_description
        new_step['parameter'] = new_parameter_ids
        image_processing_db.step.insert_one(new_step)


def copy_parameter_in_database(image_processing_db, parameter_ids, original_step_name, new_step_name):
    new_parameter_ids = parameter_ids
    for i, current_parameter_id in enumerate(parameter_ids):
        new_parameter = list(image_processing_db.parameter.find({"_id": current_parameter_id}, {'_id': 0}))[0]
        new_parameter['name'] = new_parameter['name'].replace('_' + original_step_name, '_' + new_step_name)
        text_index = 1
        while text_index < 5 and new_parameter["text" + str(text_index)]:
            new_parameter["text" + str(text_index)] = new_parameter["text" + str(text_index)].replace('_' + original_step_name, '_' + new_step_name)
            text_index = text_index + 1
        # Insert new parameter and store Ids
        new_parameter_ids[i] = image_processing_db.parameter.insert_one(new_parameter).inserted_id
        is_global_parameter = ("globalparameters" in original_step_name.lower())
        if is_global_parameter:
            field = 'inputField'
        else:
            field = 'outputField'
        dependencies = list(image_processing_db.dependency.find({field: current_parameter_id}, {'_id': 1}))
        if dependencies:
            dependency_ids = [d['_id'] for d in dependencies]
            copy_dependencies_in_database(image_processing_db, dependency_ids, original_step_name, new_step_name, field)
    return new_parameter_ids


def copy_dependencies_in_database(image_processing_db, dependency_ids, original_step_name, new_step_name, field):
    for current_dependency_id in dependency_ids:
        current_dependency = list(image_processing_db.dependency.find({"_id": current_dependency_id}, {'_id': 0}))[0]
        field_name = list(image_processing_db.parameter.find({'_id': current_dependency[field]}))[0]['name']
        new_field_name = field_name.replace('_' + original_step_name, '_' + new_step_name)
        new_field_id = list(image_processing_db.parameter.find({'name': new_field_name}, {'_id': 1}))[0]['_id']
        new_dependency = current_dependency
        new_dependency[field] = new_field_id
        new_dependency['pattern'] = new_dependency['pattern'].replace('_' + original_step_name, '_' + new_step_name)
        image_processing_db.dependency.insert_one(new_dependency)


def delete_step_and_references_from_database(image_proccessing_db, step_name):
    step = list(image_proccessing_db.step.find({"name": step_name}))[0]
    step_id = step['_id']
    # delete from templates
    templates_referencing_step = list(image_proccessing_db.template.find({"steps": step['_id']}))
    if templates_referencing_step:
        for template_referencing_step in templates_referencing_step:
            updated_steps = template_referencing_step['steps']
            updated_steps.remove(step_id)
            image_proccessing_db.template.update_one({'_id': template_referencing_step['_id']}, {'$set': {"steps": updated_steps}})
    # Delete parameters and dependencies based on it
    parameter_ids = step['parameter']
    for current_parameter_id in parameter_ids:
        image_proccessing_db.dependency.remove({"outputField": current_parameter_id})
        image_proccessing_db.parameter.remove({'_id': current_parameter_id})
    # Delete step
    image_proccessing_db.step.remove({'_id': step_id})
