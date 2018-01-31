import requests, json, random, os, math, datetime, bson, re
from flask import render_template, request
from app import app #, mongo
from pymongo import MongoClient
from time import gmtime, strftime
from collections import OrderedDict
from datetime import datetime

outputDictionary = {"_id":0,"creationDate":1,"args":1,"serviceId":1, "state":1,"modificationDate":1}
@app.route('/', defaults={'jacsServiceIndex': None}, methods=['GET','POST'])
@app.route('/<jacsServiceIndex>', methods=['GET','Post'])
#@app.route('/index', methods=['GET','POST'])
def index(jacsServiceIndex):
    #get all that have name lightsheetProcessing (so it is the parent job), dont show the id, show creationDate and args
    connection = MongoClient()
    db = connection.jacs
    findDictionary = {"name": "lightsheetProcessing"}
    parentServiceData = getParentServiceData(db, findDictionary, outputDictionary, jacsServiceIndex)

    pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']    
    pipelineSteps = []
    defaultFilePrefix = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'
    currentStepIndex = 0;

    for currentStep in pipelineOrder:
        #Check if currentStep was used in previous service
        if (jacsServiceIndex is not None) and (currentStep in parentServiceData[int(jacsServiceIndex)]["args"][3]):
            fileName = parentServiceData[int(jacsServiceIndex)]["args"][1] + str(currentStepIndex) + '_' + currentStep + '.json'
            currentStepIndex = currentStepIndex+1
            editState = 'enabled'
            checkboxState = 'checked'
        else:
            fileName = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'+ currentStep +'.json'
            editState = 'disabled'
            checkboxState = ''
        json_data = json.load(open(fileName), object_pairs_hook=OrderedDict)
        json_string = json.dumps(json_data, indent=4, separators=(',', ': '))
        json_string = re.sub(r'\[.*?\]', lambda m: m.group().replace("\n", ""), json_string, flags=re.DOTALL)
        json_string = re.sub(r'\[.*?\]', lambda m: m.group().replace(" ", ""), json_string, flags=re.DOTALL)
        pipelineSteps.append({
            'stepName': currentStep,
            'stepDescription':"",
            'inputJson': json_string,
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
        
        davidTest_json_data["args"].extend(("-allSelectedStepNames",allSelectedStepNames[0:-2]))
        davidTest_json_data["args"].extend(("-allSelectedTimePoints",allSelectedTimePoints[0:-2]))
        if step>0:
            r = requests.post('http://10.36.13.18:9000/api/rest-v2/async-services/lightsheetProcessing',
                              headers=headers,
                              data=json.dumps(davidTest_json_data))
       
    
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps,
                           parentServiceData=parentServiceData)

@app.route('/job_status', defaults={'jacsServiceIndex': None}, methods=['GET'])
@app.route('/job_status/<jacsServiceIndex>', methods=['GET'])
def job_status(jacsServiceIndex):
    connection = MongoClient()
    db = connection.jacs
    findDictionary = {"name": "lightsheetProcessing"}
    parentServiceData = getParentServiceData(db, findDictionary, outputDictionary, jacsServiceIndex)
    statuses=[]
    if jacsServiceIndex is not None:
        findDictionary = {"parentServiceId":bson.Int64(parentServiceData[int(jacsServiceIndex)]["serviceId"])}
        childJobStatuses = getServiceData(db, findDictionary, outputDictionary)
        steps = parentServiceData[int(float(jacsServiceIndex))]["args"][3].split(", ")
       
        for i in range(0,len(steps)):
            if i<=len(childJobStatuses)-1:
                statuses.append({"step": steps[i], "status": childJobStatuses[i]["state"], "startTime": str(childJobStatuses[i]["creationDate"]), "endTime":str(childJobStatuses[i]["modificationDate"]), "elapsedTime":str(childJobStatuses[i]["modificationDate"]-childJobStatuses[i]["creationDate"])})
                if childJobStatuses[i]["state"]=="RUNNING":
                    statuses[i]["elapsedTime"] = str(datetime.utcnow()-childJobStatuses[i]["creationDate"])
            else:
                statuses.append({"step": steps[i], "status": "NOT YET QUEUED", "startTime": "N/A", "endTime":"N/A", "elapsedTime": "N/A"})
        #print(statuses)
    return render_template('job_status.html', 
                           parentServiceData=parentServiceData,
                           statuses=statuses)

def getParentServiceData(db, findDictionary, outputDictionary, jacsServiceIndex=None):
    serviceData = getServiceData(db, findDictionary, outputDictionary)
    count = 0
    for dictionary in serviceData: #convert date to nicer string
        dictionary.update((k,str(v)) for k, v in dictionary.items() if k=="creationDate")
        dictionary["selected"]=''
        dictionary["index"] = str(count)
        count=count+1
    if jacsServiceIndex is not None:
        serviceData[int(jacsServiceIndex)]["selected"] = 'selected'
    return serviceData

def getServiceData(db, findDictionary, outputDictionary):
    serviceData = list(db.jacsServiceHistory.find(findDictionary, outputDictionary))
    serviceData = serviceData + list(db.jacsService.find(findDictionary, outputDictionary))
    serviceData = sorted(serviceData, key=lambda k: k['creationDate'])
    return serviceData
