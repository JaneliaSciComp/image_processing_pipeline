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
from app.utils import buildConfigObject, writeToJSON, getChildServiceData, getParentServiceData, getHeaders, loadParameters

settings = Settings()

#Prefix for all default pipeline step json file names
defaultFileBase = settings.defaultFileBase
#Location to store json files
outputDirectoryBase = settings.outputDirectoryBase

app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        user = User(form.username.data, form.email.data,
                    form.password.data)
        db_session.add(user)
        flash('Thanks for registering')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login')
def login():
    return render_template('login.html', logged_in=False)

@app.route('/submit', methods=['GET','POST'])
def submit():
    if request.method == 'POST':
        keys = request.form.keys()
        for k in iter(keys):
            print(k)
    return 'form submitted'

@app.route('/', defaults={'jacsServiceIndex': None}, methods=['GET','POST'])
@app.route('/<jacsServiceIndex>', methods=['GET','Post'])
def index(jacsServiceIndex):

    config = buildConfigObject()
    #index is the function to execute when url '/' or '/<jacsServiceIndex>' is reached and takes in the currently selected job index, if any

    #Access jacs database to get parent job service information
    parentServiceData = getParentServiceData(jacsServiceIndex)

    #Order of pipeline steps
    pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']

    #For each step, load either the default json files or the stored json files from a previously selected run
    pipelineSteps = []
    currentStepIndex = 0;

    for index, step in enumerate(config['steps']): # TODO make sure steps are ordered based on ordering
        currentStep = step.name
        #Check if currentStep was used in previous service
        if (jacsServiceIndex is not None) and (jacsServiceIndex!="favicon.ico") and (currentStep in parentServiceData[int(float(jacsServiceIndex))]["args"][3]):
            fileName = parentServiceData[int(jacsServiceIndex)]["args"][1] + str(currentStepIndex) + '_' + currentStep + '.json'
            loadParameters(fileName)
            currentStepIndex = currentStepIndex+1
            #If loading previous run parameters for specific step, then it should be checked and editable
            editState = 'enabled'
            checkboxState = 'checked'
        else:
            fileName = defaultFileBase + currentStep +'.json'
            editState = 'disabled'
            checkboxState = ''
        #Reformat json data into a more digestable format
        jsonData = json.load(open(fileName), object_pairs_hook=OrderedDict)
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
        client = MongoClient(settings.mongo)
        lightsheetDB = client.lightsheet
        numSteps = 0
        allSelectedStepNames=""
        allSelectedTimePoints=""
        stepParameters=[]
        for currentStep in pipelineOrder:
            text = request.form.get(currentStep) #will be none if checkbox is not checked
            if text is not None:
                if numSteps==0:
                    #Create new document in jobs collection in lightsheet database and create json output directory
                    newId = lightsheetDB.jobs.insert_one({"steps":{}}).inserted_id
                    outputDirectory = outputDirectoryBase + str(newId) + "/"
                    postBody = { "processingLocation": "LSF_JAVA", 
                                 "args": ["-jsonDirectory",outputDirectory],
                                 "resources": {"gridAccountId": "lightsheet"}}
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
                allSelectedStepNames = allSelectedStepNames+currentStep+", "
                allSelectedTimePoints = allSelectedTimePoints+str(numTimePoints)+", "
                numSteps+=1
        
        if numSteps>0:
            #Finish preparing the post body
            postBody["args"].extend(("-allSelectedStepNames",allSelectedStepNames[0:-2]))
            postBody["args"].extend(("-allSelectedTimePoints",allSelectedTimePoints[0:-2]))
            #postBody["errorPath"] = outputDirectory
            #postBody["outputPath"] = outputDirectory
            #Post to JACS

         #   requestOutput = requests.post(settings.lightsheetProcessing,
            requestOutput = requests.post(settings.lightsheetProcessing,
                                           headers=getHeaders,
                                           data=json.dumps(postBody))
            requestOutputJsonified = requestOutput.json()
            #Store information about the job in the lightsheet database
            currentLightsheetCommit = subprocess.check_output(['git', '--git-dir', '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/.git', 'rev-parse', 'HEAD']).strip().decode("utf-8")
            lightsheetDB.jobs.update_one({"_id":newId},{"$set": {"jacs_id":requestOutputJsonified["_id"], "lightsheetCommit":currentLightsheetCommit, "jsonDirectory":outputDirectory, "steps": stepParameters}})
    
    #Return index.html with pipelineSteps and parentServiceData
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           parentServiceData=parentServiceData,
                           logged_in=True,
                           config = config)

@app.route('/job_status', defaults={'jacsServiceIndex': None}, methods=['GET'])
@app.route('/job_status/<jacsServiceIndex>', methods=['GET'])
def job_status(jacsServiceIndex):
    #job_status is the function to execute when url '/job_status' or '/job_status/<jacsServiceIndex>' is reached and takes in the currently selected job index, if any

    #For now, get information from jacs database directly to monitor parent and child job statuses

    parentServiceData = getParentServiceData(jacsServiceIndex)
    childSummarizedStatuses=[]
    if jacsServiceIndex is not None:
        #If a specific parent job is selected, find all the child job status information and store the step name, status, start time, endtime and elapsedTime
        childJobStatuses = getChildServiceData( parentServiceData[int(jacsServiceIndex)]["_id"] )
        steps = parentServiceData[int(jacsServiceIndex)]["args"][3].split(", ")
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
                           logged_in=True)
@app.route('/search')
def search():
    return render_template('search.html',
                           logged_in=True)
