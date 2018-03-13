import requests, json, random, os, math, datetime, bson, re, subprocess
from flask import render_template, request
from pymongo import MongoClient
from time import gmtime, strftime
from collections import OrderedDict
from datetime import datetime
from pprint import pprint
from app import app
from app.settings import Settings
from app.models import AppConfig
from app.utils import buildConfigObject, writeToJSON, getChildServiceDataFromJACS, getParentServiceDataFromJACS
from app.utils import getServiceDataFromDB, getHeaders, loadParameters, getAppVersion, getPipelineStepNames

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

#@app.route('/', defaults={'serviceIndex': None}, methods=['GET','POST'])
#@app.route('/<serviceIndex>', methods=['GET','Post'])
#def index(serviceIndex):
#    serviceIndex = request.args.get('jacsServiceIndex')
@app.route('/', methods=['GET','POST'])
def index():
    jobIndex = request.args.get('jacsServiceIndex')
   
    #Mongo client
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet

    config = buildConfigObject()
    #index is the function to execute when url '/' or '/<jobIndex>' is reached and takes in the currently selected job index, if any

    #Access jacs database to get parent job service information
    serviceData = getServiceDataFromDB(lightsheetDB)
    jobSelected = False;
    if jobIndex is not None:
        jobIndex = int(jobIndex)
        serviceData[jobIndex]["selected"]='selected'
        jobSelected = True;
  
    #Order of pipeline steps
    pipelineOrder = getPipelineStepNames()

    #For each step, load either the default json files or the stored json files from a previously selected run
    pipelineSteps = []
    jobStepIndex = 0;
    
    for step in config['steps']: # TODO make sure steps are ordered based on ordering
        currentStep = step.name
        #Check if currentStep was used in previous service
        if jobSelected and (currentStep in serviceData[jobIndex]["selectedStepNames"]):
            arrayOfStepDictionaries = serviceData[jobIndex]["steps"]
            #If loading previous run parameters for specific step, then it should be checked and editable
            editState = 'enabled'
            checkboxState = 'checked'
            jsonString = json.dumps(arrayOfStepDictionaries[jobStepIndex]["parameters"], indent=4, separators=(',', ': '));
            jobStepIndex = jobStepIndex+1
        else: #Defaults
            fileName = defaultFileBase + currentStep +'.json'
            editState = 'disabled'
            checkboxState = ''
            jsonData = json.load(open(fileName), object_pairs_hook=OrderedDict)
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
        numSteps = 0
        allSelectedStepNames=""
        allSelectedTimePoints=""
        stepParameters=[]
  
        userDefinedJobName=[]
        for currentStep in pipelineOrder:
            text = request.form.get(currentStep) #will be none if checkbox is not checked
            if text is not None:
                if numSteps==0:
                    #Create new document in jobs collection in lightsheet database and create json output directory
                    newId = lightsheetDB.jobs.insert_one({"steps":{}}).inserted_id
                    outputDirectory = outputDirectoryBase + str(newId) + "/"
                    postBody = { "processingLocation": "LSF_JAVA",
                                 "args": ["-configDirectory",outputDirectory],
                                 "resources": {"gridAccountId": "lightsheet"}
                                 #,"queueId":"jacs-dev"
                    }
                    os.mkdir(outputDirectory)
                #Write json files
                fileName=str(numSteps) + "_" + currentStep + ".json"
                fh = open(outputDirectory + fileName,"w")
                fh.write(text)
                fh.close()
                #Store step parameters and step names/times to use as arguments for the post
                jsonifiedText = json.loads(text, object_pairs_hook=OrderedDict)
                stepParameters.append({"stepName":currentStep, "parameters": jsonifiedText})
                numTimePoints = math.ceil(1+(jsonifiedText["timepoints"]["end"] - jsonifiedText["timepoints"]["start"])/jsonifiedText["timepoints"]["every"])
                allSelectedStepNames = allSelectedStepNames+currentStep+","
                allSelectedTimePoints = allSelectedTimePoints+str(numTimePoints)+", "
                numSteps+=1
        
        if numSteps>0:
            #Finish preparing the post body
            allSelectedStepNames = allSelectedStepNames[0:-1]
            allSelectedTimePoints = allSelectedTimePoints[0:-2]
            postBody["args"].extend(("-allSelectedStepNames",allSelectedStepNames))
            postBody["args"].extend(("-allSelectedTimePoints",allSelectedTimePoints))
            #postBody["errorPath"] = outputDirectory
            #postBody["outputPath"] = outputDirectory
            #Post to JACS
            requestOutput = requests.post(settings.devOrProductionJACS + '/async-services/lightsheetProcessing',
                                           headers=getHeaders(),
                                           data=json.dumps(postBody))
 
            requestOutputJsonified = requestOutput.json()
            #Store information about the job in the lightsheet database
            currentLightsheetCommit = subprocess.check_output(['git', '--git-dir', settings.pipelineGit, 'rev-parse', 'HEAD']).strip().decode("utf-8")
            if not userDefinedJobName:
                userDefinedJobName = requestOutputJsonified["_id"]
            lightsheetDB.jobs.update_one({"_id":newId},{"$set": {"jacs_id":requestOutputJsonified["_id"], "jobName": userDefinedJobName,
                                                                 "lightsheetCommit":currentLightsheetCommit, "jsonDirectory":outputDirectory, 
                                                                 "selectedStepNames": allSelectedStepNames, "steps": stepParameters}})
    
    
    parentServiceData = getParentServiceDataFromJACS(lightsheetDB, jobIndex)
    
    #Return index.html with pipelineSteps and serviceData
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           serviceData=serviceData,
                           parentServiceData=parentServiceData,
                           logged_in=True,
                           config = config,
                           version = app_version)

@app.route('/job_status/', methods=['GET'])
def job_status():
    jobIndex = request.args.get('jacsServiceIndex')
    #Mongo client
    client = MongoClient(settings.mongo)
    #lightsheetDB is the database containing lightsheet job information and parameters
    lightsheetDB = client.lightsheet

    #For now, get information from jacs database directly to monitor parent and child job statuses
    parentServiceData = getParentServiceDataFromJACS(lightsheetDB, jobIndex)
    childSummarizedStatuses=[]

    if jobIndex is not None:
        jobIndex=int(jobIndex)
        
        #If a specific parent job is selected, find all the child job status information and store the step name, status, start time, endtime and elapsedTime
        childJobStatuses = getChildServiceDataFromJACS( parentServiceData[jobIndex]["_id"] )
        steps = parentServiceData[jobIndex]["args"][3].split(",")
        for i in range(0,len(steps)):
            if i<=len(childJobStatuses)-1:
                childSummarizedStatuses.append({"step": steps[i], "status": childJobStatuses[i]["state"], "startTime": str(childJobStatuses[i]["creationDate"]), "endTime":str(childJobStatuses[i]["modificationDate"]), "elapsedTime":str(childJobStatuses[i]["modificationDate"]-childJobStatuses[i]["creationDate"])})
                if childJobStatuses[i]["state"]=="RUNNING":
                    childSummarizedStatuses[i]["elapsedTime"] = str(datetime.now(utils.eastern)-childJobStatuses[i]["creationDate"])
            else:
                childSummarizedStatuses.append({"step": steps[i], "status": "NOT YET QUEUED", "startTime": "N/A", "endTime":"N/A", "elapsedTime": "N/A"})

    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentServiceData=parentServiceData,
                           childSummarizedStatuses=childSummarizedStatuses,
                           logged_in=True,
                           version = app_version)
@app.route('/search')
def search():
    return render_template('search.html',
                           logged_in=True,
                           version = app_version)

@app.route('/config/<uuid>', methods=['GET','POST'])
def config(uuid):
 #   if numsteps>0
    client = MongoClient(settings.mongo)
    lightsheetDB = client.lightsheet
    if request.method=='POST':
        #put it in database
        #return the address to it, which will be the db _id
        newId = lightsheetDB.jobs.insert_one({"jobName": userDefinedJobName,
                                              "lightsheetCommit":currentLightsheetCommit, "jsonDirectory":outputDirectory, 
                                              "selectedStepNames": allSelectedStepNames, "steps": stepParameters}).inserted_id
        #run jacs which will call get....
        lightsheetDB.jobs.update_one({"_id":newId},{"$set": {"jacs_id":requestOutputJsonified["_id"]}})
    if request.method=='GET':
        #write out json file to current directory from database?
    
    #request.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({'text': 'lalala'})
