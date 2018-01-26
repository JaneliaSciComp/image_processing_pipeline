import requests, json, random, os, math, datetime
from flask import render_template, request
from app import app #, mongo
from pymongo import MongoClient
from time import gmtime, strftime
from collections import OrderedDict
import bson

@app.route('/', defaults={'jacsServiceIndex': None}, methods=['GET','POST'])
@app.route('/<jacsServiceIndex>', methods=['GET','Post'])
#@app.route('/index', methods=['GET','POST'])
def index(jacsServiceIndex):
    #get all that have name lightsheetProcessing (so it is the parent job), dont show the id, show creationDate and args
    connection = MongoClient()
    db = connection.jacs
    serviceHistory = getServiceHistory(db, jacsServiceIndex)

    pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']    
    pipelineSteps = []
    defaultFilePrefix = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'
    currentStepIndex = 0;

    for currentStep in pipelineOrder:
        #Check if currentStep was used in previous service
        if (jacsServiceIndex is not None) and (currentStep in serviceHistory[int(jacsServiceIndex)]["args"][3]):
            fileName = serviceHistory[int(jacsServiceIndex)]["args"][1] + str(currentStepIndex) + '_' + currentStep + '.json'
            currentStepIndex = currentStepIndex+1
            editState = 'enabled'
            checkboxState = 'checked'
        else:
            fileName = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'+ currentStep +'.json'
            editState = 'disabled'
            checkboxState = ''
        json_data = json.load(open(fileName))
        pipelineSteps.append({
            'stepName': currentStep,
            'inputJson': json.dumps(json_data, indent=4, separators=(',', ': ')),
            'state': editState,
            'checkboxState': checkboxState
        })
    
    headers = {'content-type': 'application/json', 'USERNAME': 'lightsheet'}
    

    if request.method == 'POST':
        datetime_and_randint = strftime("%Y%m%d_%H%M%S_", gmtime())+str(random.randint(1,100)).zfill(3)
        output_directory = "/groups/lightsheet/lightsheet/home/ackermand/interface_output/"+datetime_and_randint+"/"
        os.mkdir(output_directory)
        davidTest_json_data = { "processingLocation": "LSF_JAVA", 
                                "args": ["-jsonDirectory",output_directory],
                                "resources": {"gridAccountId": "lightsheet"}}
        step = 0
        allSelectedStepNames=""
        allSelectedTimePoints=""
        for currentStep in pipelineOrder:
            text = request.form.get(currentStep) #will be none if checkbox is not checked
            if text is not None:
                fileName=str(step) + "_" + currentStep + ".json"
                fh = open(output_directory + fileName,"w")
                fh.write(text)
                fh.close()
                jsonifiedText = json.loads(text, object_pairs_hook=OrderedDict)
                numTimePoints = math.ceil(1+(jsonifiedText["timepoints"]["end"] - jsonifiedText["timepoints"]["start"])/jsonifiedText["timepoints"]["every"])
                allSelectedStepNames = allSelectedStepNames+currentStep+", "
                allSelectedTimePoints = allSelectedTimePoints+str(numTimePoints)+", "
                step+=1
                #allSelectedTimePoints.append(numTimePoints)
                #allSelectedScriptNames.append(fileName)
        
        davidTest_json_data["args"].extend(("-allSelectedStepNames",allSelectedStepNames[0:-2]))
        davidTest_json_data["args"].extend(("-allSelectedTimePoints",allSelectedTimePoints[0:-2]))
        r = requests.post('http://10.36.13.18:9000/api/rest-v2/async-services/lightsheetProcessing',
                          headers=headers,
                          data=json.dumps(davidTest_json_data))
       
    
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           serviceHistory=serviceHistory)

@app.route('/job_status', defaults={'jacsServiceIndex': None}, methods=['GET'])
@app.route('/job_status/<jacsServiceIndex>', methods=['GET'])
def job_status(jacsServiceIndex):
    connection = MongoClient()
    db = connection.jacs
    serviceHistory = getServiceHistory(db, jacsServiceIndex)
    statuses=[]
    if jacsServiceIndex is not None:
        childJobStatuses = list(db.jacsServiceHistory.find({"parentServiceId":bson.Int64(serviceHistory[int(jacsServiceIndex)]["serviceId"])},{"_id":0, "args":1, "state":1, "events":1}))
        steps = serviceHistory[int(jacsServiceIndex)]["args"][3].split(", ")
        #print(serviceHistory[int(jacsServiceIndex)]["serviceId"])
        print(steps)
        print(childJobStatuses)
        
        for i in range(0,len(steps)):
            if i<=len(childJobStatuses)-1:
                statuses.append(steps[i] + " status: " + childJobStatuses[i]["state"])
            else:
                statuses.append(steps[i] + " status: NOT YET QUEUED")
       # print(statusString)
    return render_template('job_status.html', 
                           serviceHistory=serviceHistory,
                           statuses=statuses)

def getServiceHistory(db,jacsServiceIndex):
    count = 0
    serviceHistory = list(db.jacsServiceHistory.find({"name": "lightsheetProcessing"},{"_id":0,"creationDate":1,"args":1,"serviceId":1})) #get all that have name lightsheetProcessing (so it is the parent job), dont show the id, show creationDate and args
    for dictionary in serviceHistory: #convert date to nicer string
        dictionary.update((k,str(v)) for k, v in dictionary.items() if k=="creationDate")
        dictionary["selected"]=''
        dictionary["index"] = str(count)
        count=count+1
    if jacsServiceIndex is not None:
        serviceHistory[int(jacsServiceIndex)]["selected"] = 'selected'
    return serviceHistory
