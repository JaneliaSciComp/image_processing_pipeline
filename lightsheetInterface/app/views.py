import requests, json, random, os, math, datetime, bson, re, subprocess, ipdb
from flask import render_template, request, jsonify, abort
from pymongo import MongoClient
from time import gmtime, strftime
from collections import OrderedDict
from datetime import datetime
from pprint import pprint
from app import app
from app.settings import Settings
from app.models import AppConfig
from app.utils import buildConfigObject, writeToJSON, getChildServiceDataFromJACS, getParentServiceDataFromJACS, eastern, UTC
from app.utils import updateDBStatesAndTimes, getJobInfoFromDB, getConfigurationsFromDB, getHeaders, loadParameters, getAppVersion, getPipelineStepNames, parseJsonData
from bson.objectid import ObjectId

settings = Settings()

#Prefix for all default pipeline step json file names
defaultFileBase = settings.defaultFileBase
#Location to store json files
outputDirectoryBase = settings.outputDirectoryBase

app_version = getAppVersion(app.root_path)

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
                version = app_version)

@app.route('/login')
def login():
    return render_template('login.html',
                logged_in=False,
                version = app_version)

@app.route('/submit', methods=['GET','POST'])
def submit():
    if request.method == 'POST':
        keys = request.form.keys()
        for k in iter(keys):
            print(k)
    return 'form submitted'

@app.route('/', methods=['GET','POST'])
def index():
    jobIndex = request.args.get('jacsServiceIndex')
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet
    if jobIndex is not None:
        jobSelected=True
        selectedJobInfo = getJobInfoFromDB(lightsheetDB, jobIndex)
        selectedJobInfo = selectedJobInfo[0]
        arrayOfStepDictionaries = selectedJobInfo["steps"]
    else:
        jobSelected=False
    #Mongo client

    config = buildConfigObject()
    #index is the function to execute when url '/' or '/<jobIndex>' is reached and takes in the currently selected job index, if any

    #Access jacs database to get parent job service information
    # allJobInfo,jobSelected, _ = getAllJobInfoFromDB(lightsheetDB, jobIndex)

    #For each step, load either the default json files or the stored json files from a previously selected run
    pipelineSteps = []
    jobStepIndex = 0
    for step in config['steps']:
        currentStep = step.name
        #Check if currentStep was used in previous service
        if jobSelected and (currentStep in selectedJobInfo["selectedStepNames"]):
            #If loading previous run parameters for specific step, then it should be checked and editable
            editState = 'enabled'
            checkboxState = 'checked'
            jsonString = json.dumps(arrayOfStepDictionaries[jobStepIndex]["parameters"], indent=4, separators=(',', ': '));
            jobStepIndex = jobStepIndex+1
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
                    stepParameters.append({"name":currentStep, "state":"NOT YET QUEUED", "creationTime":"N/A", "endTime":"N/A", "elapsedTime":"N/A","parameters": jsonifiedText})
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
    parentJobInfo = getJobInfoFromDB(lightsheetDB)
    for currentJobInfo in parentJobInfo:
        currentJobInfo.update({"selected":""})
        if currentJobInfo["_id"]==ObjectId(jobIndex):
            currentJobInfo.update({"selected":"selected"})
  
    #Return index.html with pipelineSteps and serviceData
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           parentJobInfo = parentJobInfo,
                           logged_in=True,
                           config = config,
                           version = app_version,
                           formData = formObject,
                           jobIndex = jobIndex)

@app.route('/job_status/', methods=['GET'])
def job_status():
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet

    jobIndex = request.args.get('jacsServiceIndex')
    #Mongo client
    updateDBStatesAndTimes(lightsheetDB)
    parentJobInfo = getJobInfoFromDB(lightsheetDB)
        
    childJobInfo=[]
    if jobIndex is not None:
        for currentJobInfo in parentJobInfo:
            currentJobInfo.update({"selected":""})
            if currentJobInfo["_id"]==ObjectId(jobIndex):
                currentJobInfo.update({"selected":"selected"})
        childJobInfo = getJobInfoFromDB(lightsheetDB, jobIndex)
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

@app.route('/config/<_id>', methods=['GET'])
def config(_id):
    stepName = request.args.get('stepName')
    output=getConfigurationsFromDB(_id, stepName)
    if output==404:
        abort(404)
    else:
        return jsonify(output)
