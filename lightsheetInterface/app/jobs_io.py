# Contains functions to load jobs and submit jobs
import re, json
from flask import abort

from flask_login import current_user
from mongoengine.queryset.visitor import Q
from app.models import Step, Parameter
from app import app
from app.utils import submit_to_jacs, get_job_step_data_from_db, get_parameters
from bson.objectid import ObjectId
from collections import OrderedDict


# If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
def submit_the_job_to_db_and_jacs(config_server_url, form_json, reparameterize, image_processing_db, image_processing_db_id, submission_address=None, step_or_template_name=None):
    app.logger.info('Post json data: {0}'.format(form_json))
    app.logger.info('Current Step Or Template: {0}'.format(step_or_template_name))

    if form_json != '[]' and form_json is not None:
        # get the name of the job first
        job_name = ''
        if 'jobName' in form_json.keys():
            job_name = form_json['jobName']
            del (form_json['jobName'])

        reformatted_data, remaining_step_names = reformat_data_to_post(form_json)
        # Prepare the db data
        data_to_post_to_db = {
            "jobName": job_name,
            "username": current_user.username,
            "submissionAddress": submission_address,
            "stepOrTemplateName": step_or_template_name,
            "state": "NOT YET QUEUED",
            "containerVersion": "placeholder",
            "remainingStepNames": remaining_step_names,
            "steps": reformatted_data
        }

        # Insert the data to the db
        image_processing_db_id = post_to_db(data_to_post_to_db, image_processing_db, image_processing_db_id, reparameterize)

        # Submit to jacs
        submission_status = submit_to_jacs(config_server_url, image_processing_db, image_processing_db_id, reparameterize)
        return submission_status


# reformat data for job resubmission
def reformat_data_to_post(posted_data, for_submission=True):
    unordered_reformatted_data = []
    if posted_data and posted_data != {}:
        for step in posted_data.keys():
            step_parameters_reformatted, parameters_to_empty = initial_reformatting_of_step_parameters(posted_data, step)
            step_parameters_reformatted = final_reformatting_of_step_parameters(step_parameters_reformatted, parameters_to_empty)

            # add some optional paramters
            step_result = {}
            step_result['name'] = step
            for submission_parameter in ['type', 'bindPaths', 'pause']:
                if submission_parameter in posted_data[step].keys():
                    step_result[submission_parameter] = posted_data[step][submission_parameter]

            if for_submission:
                step_result['state'] = 'NOT YET QUEUED'
            step_result['parameters'] = step_parameters_reformatted
            unordered_reformatted_data.append(OrderedDict(step_result))

            app.logger.info(unordered_reformatted_data)

        reformatted_data, remaining_step_names = reorder_steps_and_add_final_step_parameters(unordered_reformatted_data)
    return reformatted_data, remaining_step_names


def initial_reformatting_of_step_parameters(posted_data, step):
    p = 'parameters'
    parameters_to_empty = []
    # first part: get the parameter values into lists
    step_parameters_reformatted = {}
    sorted_parameters = sorted(posted_data[step][p].keys())
    for parameter_key in sorted_parameters:
        parameter_name = parameter_key.rsplit('_', 1)[0]

        # Find checkboxes and deal with them separately
        if 'emptycheckbox_' in parameter_key and posted_data[step][p][parameter_key].upper() == 'TRUE':
            parameters_to_empty.append(parameter_name.split('_', 1)[-1])

        if ('-' in parameter_key) and Parameter.objects.filter(Q(formatting='R') & Q(name=parameter_key.split('-')[0])):
            range_key = parameter_key.split('-')[1]  # start, end or every
            param_value_set = step_parameters_reformatted[parameter_name] if parameter_name in step_parameters_reformatted else {}
            # move the parts of the range parameter to the right key of the object
            if range_key in ['start', 'every', 'end']:
                current_value = posted_data[step][p][parameter_key]
                param_value_set[range_key] = float(current_value) if current_value is not '' and current_value != "[]" else ''
                step_parameters_reformatted[parameter_name] = param_value_set
        else:  # no range
            param_value_set = []
            # check if current value is a float within a string and needs to be converted
            current_value = posted_data[step][p][parameter_key]

            if re.match("[-+]?[0-9]*\.?[0-9]*.$", current_value) is None:  # no float
                try:
                    tmp = json.loads(current_value)
                    param_value_set.append(tmp)
                except ValueError:
                    param_value_set.append(current_value)
            else:  # it's actual a float value -> get the value
                param_value_set.append(float(current_value))

            step_parameters_reformatted[parameter_name] = param_value_set
    return step_parameters_reformatted, parameters_to_empty


def final_reformatting_of_step_parameters(step_parameters_reformatted, parameters_to_empty):
    # cleanup step / second part: for lists with just one element, get the element
    for parameter_name in step_parameters_reformatted:
        if parameter_name in parameters_to_empty:
            step_parameters_reformatted[parameter_name] = []
        else:
            if type(step_parameters_reformatted[parameter_name]) is list:
                if len(step_parameters_reformatted[parameter_name]) == 1:
                    step_parameters_reformatted[parameter_name] = step_parameters_reformatted[parameter_name][0]
                else:
                    for elem in step_parameters_reformatted[parameter_name]:
                        if elem == "" and len(set(step_parameters_reformatted[parameter_name])) == 1:
                            step_parameters_reformatted[parameter_name] = []
                            break
    return step_parameters_reformatted


def reorder_steps_and_add_final_step_parameters(unordered_reformatted_data):
    reformatted_data = []
    remaining_step_names = []
    all_steps = Step.objects.all().order_by('order')
    if all_steps:
        for step in all_steps:
            current_step_dictionary = next((dictionary for dictionary in unordered_reformatted_data if dictionary["name"] == step.name), None)
            if current_step_dictionary:
                current_step_dictionary["codeLocation"] = step.codeLocation if step.codeLocation else ""
                if step.steptype == "Sp":
                    current_step_dictionary["entryPointForSpark"] = step.entryPointForSpark
                if step.submit:
                    remaining_step_names.append(current_step_dictionary["name"])
                reformatted_data.append(current_step_dictionary)
    return reformatted_data, remaining_step_names


# new parse data, don't create any flask forms
def parse_json_data_no_forms(data, step_name, config):
    step = [step for step in config['steps'] if step['name'] == step_name]
    step_parameters = get_parameters(step[0].parameter)
    # Check structure of incoming data
    if 'parameters' in data:
        parameter_data = data['parameters']
    else:
        parameter_data = data

    keys = parameter_data.keys()
    fsr_dictionary = {'F': 'frequent', 'S': 'sometimes', 'R': 'rare'}
    result = {'frequent': {}, 'sometimes': {}, 'rare': {}}
    if keys is not None:
        # For each key, look up the parameter type and add parameter to the right type of form based on that:
        for key in keys:
            key_with_appended_step_name_assured = key.rsplit('_', 1)[0] + '_' + step_name
            param = [param for param in step_parameters if param['name'] == key_with_appended_step_name_assured]
            if param and key:  # check if key now exists
                param = param[0]
                if type(parameter_data[key]) is list and len(parameter_data[key]) == 0:
                    parameter_data[key] = ''
                elif parameter_data[key] == 'None':
                    parameter_data[key] = ''
                frequency = fsr_dictionary[param['frequency']]
                result[frequency][key] = {'config': param, 'data': parameter_data[key]}
    return result


def post_to_db(data_to_post_to_db, image_processing_db, image_processing_db_id, reparameterize):
    if reparameterize:
        image_processing_db_id = ObjectId(image_processing_db_id)
        sub_dict = {k: data_to_post_to_db[k] for k in (
            'jobName', 'submissionAddress', 'stepOrTemplateName', 'state', 'containerVersion',
            'remainingStepNames')}
        image_processing_db.jobs.update_one({"_id": image_processing_db_id}, {"$set": sub_dict})
        for current_step_dictionary in data_to_post_to_db['steps']:
            update_output = image_processing_db.jobs.update_one({"_id": image_processing_db_id, "steps.name": current_step_dictionary["name"]}, {"$set": {"steps.$": current_step_dictionary}})
            if update_output.matched_count == 0:  # Then new step
                image_processing_db.jobs.update_one({"_id": image_processing_db_id}, {"$push": {"steps": current_step_dictionary}})

    else:
        image_processing_db_id = image_processing_db.jobs.insert_one(data_to_post_to_db).inserted_id
    return image_processing_db_id


def load_preexisting_job(image_processing_db, image_processing_db_id, reparameterize, configuration_object):
    preexisting_job_step_data, overall_job_information = get_job_step_data_from_db(image_processing_db, image_processing_db_id)
    able_to_reparameterize = True
    succeeded_but_latter_step_failed = []

    if preexisting_job_step_data:
        if (preexisting_job_step_data[-1]["pause"] == 0 and preexisting_job_step_data[-1]["state"] == "SUCCESSFUL") \
                or any((step["state"] in "RUNNING CREATED") for step in preexisting_job_step_data):
            # Can't reparameterize if last step already completed successfully or if any step hasn't stopped
            able_to_reparameterize = False

        error_step_index = next((i for i, step in enumerate(preexisting_job_step_data) if step["state"] == "ERROR"), None)
        if error_step_index:
            for i in range(error_step_index):
                succeeded_but_latter_step_failed.append(preexisting_job_step_data[i]["name"])

    job_name = None
    if reparameterize == "true" and image_processing_db_id:
        job_name = overall_job_information['jobName']
        reparameterize = True
        remaining_step_names = overall_job_information["remainingStepNames"]
        if not able_to_reparameterize:
            abort(404)
    else:
        reparameterize = False

    workflow_steps, load_status = format_steps_for_loading_in_view(preexisting_job_step_data, image_processing_db_id, reparameterize, configuration_object, remaining_step_names, succeeded_but_latter_step_failed)
    return workflow_steps, load_status, job_name, overall_job_information['username']


def format_steps_for_loading_in_view(preexisting_job_step_data, image_processing_db_id, reparameterize, configuration_object, remaining_step_names, succeeded_but_latter_step_failed):
    workflow_steps = OrderedDict()
    load_status = None
    # match data on step name
    if type(preexisting_job_step_data) is list:
        if image_processing_db_id != None:  # load data for an existing job
            for current_step_data in preexisting_job_step_data:
                if current_step_data:
                    # go through all steps and find those, which are used by the current job
                    current_step_name = current_step_data['name']
                    step = Step.objects(name=current_step_name).first()
                    checkbox_state = 'checked'
                    collapse_or_show = 'show'
                    if ("globalparameters" not in current_step_name.lower()) and reparameterize and ((current_step_name not in remaining_step_names) or (current_step_name in succeeded_but_latter_step_failed)):
                        checkbox_state = 'unchecked'
                        collapse_or_show = ''

                    loaded_parameters = parse_json_data_no_forms(current_step_data, current_step_name, configuration_object)
                    # Pipeline steps is passed to index.html for formatting the html based
                    workflow_steps[current_step_name] = {
                        'stepName': current_step_name,
                        'stepDescription': step.description,
                        'pause': current_step_data['pause'] if 'pause' in current_step_data else 0,
                        'inputJson': None,
                        'checkboxState': checkbox_state,
                        'collapseOrShow': collapse_or_show,
                        'loadedParameters': loaded_parameters
                    }
    elif type(preexisting_job_step_data) is dict:
        load_status = 'Job cannot be loaded.'
    return workflow_steps, load_status


def load_uploaded_config(uploaded_content, configuration_object):
    pipeline_steps = OrderedDict()
    if 'steps' in uploaded_content:
        steps = uploaded_content['steps']
        for s in steps:
            name = s['name']
            step_config = [step for step in configuration_object['steps'] if step['name'] == name]
            step_config = step_config[0]
            loaded_parameters = parse_json_data_no_forms(s, name, configuration_object)
            # Pipeline steps is passed to index.html for formatting the html based
            pipeline_steps[name] = {
                'stepName': name,
                'stepDescription': step_config,
                'inputJson': None,
                'state': False,
                'checkboxState': 'checked',
                'collapseOrShow': 'show',
                'loadedParameters': loaded_parameters
            }

    step_name = None
    template_name = None
    if 'stepOrTemplateName' in uploaded_content:
        step_or_template_name = uploaded_content["stepOrTemplateName"]
        if step_or_template_name.find("Step: ", 0, 6) != -1:
            step_name = step_or_template_name[6:]
        else:
            template_name = step_or_template_name[10:]

    return pipeline_steps, step_name, template_name
