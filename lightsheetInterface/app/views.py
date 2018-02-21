import requests, json, random, os, math, datetime, bson, re, subprocess
from flask import render_template, request
from app import app
from pymongo import MongoClient
from time import gmtime, strftime
from collections import OrderedDict
from datetime import datetime

#Note: The endpoint to access JACS job information is currently being created, so in the meantime and FOR NONPRODUCTION work we are accessing a local mongo server directly

#Prefix for all default pipeline step json file names
defaultFileBase = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'
#Location to store json files
outputDirectoryBase = "/groups/lightsheet/lightsheet/home/ackermand/interface_output/" 
#Header for post request
headers = {'content-type': 'application/json', 'USERNAME': 'ackermand', 'RUNASUSER': 'lightsheet'}

@app.route('/', defaults={'jacsServiceIndex': None}, methods=['GET','POST'])
@app.route('/<jacsServiceIndex>', methods=['GET','Post'])
def index(jacsServiceIndex):
    #index is the function to execute when url '/' or '/<jacsServiceIndex>' is reached and takes in the currently selected job index, if any

    #Access jacs database to get parent job service information
    client = MongoClient()
    jacsDB = client.jacs
    findDictionary = {"name": "lightsheetProcessing"}
    parentServiceData = getParentServiceData(jacsDB, findDictionary, jacsServiceIndex)

    #Order of pipeline steps
    pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']

    #For each step, load either the default json files or the stored json files from a previously selected run
    pipelineSteps = []
    currentStepIndex = 0;
    for currentStep in pipelineOrder:
        #Check if currentStep was used in previous service
        if (jacsServiceIndex is not None) and (jacsServiceIndex!="favicon.ico") and (currentStep in parentServiceData[int(float(jacsServiceIndex))]["args"][3]):
            fileName = parentServiceData[int(jacsServiceIndex)]["args"][1] + str(currentStepIndex) + '_' + currentStep + '.json'
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
            'stepDescription':"",
            'inputJson': jsonString,
            'state': editState,
            'checkboxState': checkboxState
        })

    pipelineSteps[0]["stepDescription"] = "Image Correction and Compression"
    pipelineSteps[1]["stepDescription"] = "Multiview Image Fusion (MF)"
    pipelineSteps[2]["stepDescription"] = "Preprocessing MF for Temporal Smoothing"
    pipelineSteps[3]["stepDescription"] = "Temporal Smoothing of MF"
    pipelineSteps[4]["stepDescription"] = "Preprocessing for 3D Drift Correction and Intensity Normalization"
    pipelineSteps[5]["stepDescription"] = "Drift and Intensity Correction"
    pipelineSteps[6]["stepDescription"] = "Filter Image Stacks and/or Max. Intensity Projections of Filtered Stacks"

    if request.method == 'POST':
        #If a job is submitted (POST request) then we have to save parameters to json files and to a database and submit the job
        #lightsheetDB is the database containing lightsheet job information and parameters
        client = MongoClient()#'mongodb://10.40.3.155:27017/')
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
            requestOutput = requests.post('http://jacs-dev.int.janelia.org:9000/api/rest-v2/async-services/lightsheetProcessing',
                                           headers=headers,
                                           data=json.dumps(postBody))
            requestOutputJsonified = requestOutput.json()
            print(requestOutputJsonified)
            #Store information about the job in the lightsheet database
            currentLightsheetCommit = subprocess.check_output(['git', '--git-dir', '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/.git', 'rev-parse', 'HEAD']).strip().decode("utf-8")
            lightsheetDB.jobs.update_one({"_id":newId},{"$set": {"jacs_id":requestOutputJsonified["_id"], "lightsheetCommit":currentLightsheetCommit, "jsonDirectory":outputDirectory, "steps": stepParameters}})
    
    #Return index.html with pipelineSteps and parentServiceData
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           parentServiceData=parentServiceData)

@app.route('/job_status', defaults={'jacsServiceIndex': None}, methods=['GET'])
@app.route('/job_status/<jacsServiceIndex>', methods=['GET'])
def job_status(jacsServiceIndex):
    #job_status is the function to execute when url '/job_status' or '/job_status/<jacsServiceIndex>' is reached and takes in the currently selected job index, if any

    #For now, get information from jacs database directly to monitor parent and child job statuses
    connection = MongoClient()
    jacsDB = connection.jacs
    findDictionary = {"name": "lightsheetProcessing"}
    parentServiceData = getParentServiceData(jacsDB, findDictionary,  jacsServiceIndex)
    childSummarizedStatuses=[]
    if jacsServiceIndex is not None:
        #If a specific parent job is selected, find all the child job status information and store the step name, status, start time, endtime and elapsedTime
        findDictionary = {"parentServiceId":bson.Int64(parentServiceData[int(jacsServiceIndex)]["serviceId"])}
        childJobStatuses = getServiceData(jacsDB, findDictionary)
        steps = parentServiceData[int(float(jacsServiceIndex))]["args"][3].split(", ")
        for i in range(0,len(steps)):
            if i<=len(childJobStatuses)-1:
                childSummarizedStatuses.append({"step": steps[i], "status": childJobStatuses[i]["state"], "startTime": str(childJobStatuses[i]["creationDate"]), "endTime":str(childJobStatuses[i]["modificationDate"]), "elapsedTime":str(childJobStatuses[i]["modificationDate"]-childJobStatuses[i]["creationDate"])})
                if childJobStatuses[i]["state"]=="RUNNING":
                    childSummarizedStatuses[i]["elapsedTime"] = str(datetime.utcnow()-childJobStatuses[i]["creationDate"])
            else:
                childSummarizedStatuses.append({"step": steps[i], "status": "NOT YET QUEUED", "startTime": "N/A", "endTime":"N/A", "elapsedTime": "N/A"})

    #Return job_status.html which takes in parentServiceData and childSummarizedStatuses
    return render_template('job_status.html', 
                           parentServiceData=parentServiceData,
                           childSummarizedStatuses=childSummarizedStatuses)

def getParentServiceData(db, findDictionary, jacsServiceIndex=None):
    #Function to get information about parent jobs from JACS database and marks currently selected job
    serviceData = getServiceData(db, findDictionary)
    count = 0
    for dictionary in serviceData: #convert date to nicer string
        dictionary.update((k,str(v)) for k, v in dictionary.items() if k=="creationDate")
        dictionary["selected"]=''
        dictionary["index"] = str(count)
        count=count+1
    if jacsServiceIndex is not None and (jacsServiceIndex!="favicon.ico"):
        serviceData[int(float(jacsServiceIndex))]["selected"] = 'selected'
    return serviceData

def getServiceData(db, findDictionary):
    #Function to get information from JACS service databases based on a findDictionary
    #Gets information about currently running and already completed jobs
    outputDictionary = {"_id":0,"creationDate":1,"args":1,"serviceId":1, "state":1,"modificationDate":1}
    serviceData = list(db.jacsServiceHistory.find(findDictionary, outputDictionary))
    serviceData = serviceData + list(db.jacsService.find(findDictionary, outputDictionary))
    serviceData = sorted(serviceData, key=lambda k: k['creationDate'])
    return serviceData
