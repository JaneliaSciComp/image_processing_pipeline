import requests, json, random, os, math, datetime
from flask import render_template, request
from app import app #, mongo
from pymongo import MongoClient
from time import gmtime, strftime

@app.route('/', methods=['GET','POST'])
#@app.route('/index', methods=['GET','POST'])
def index():
    pipelineOrder = ['clusterPT', 'clusterMF', 'localAP', 'clusterTF', 'localEC', 'clusterCS', 'clusterFR']
    
    pipelineSteps = []
    for currentStep in pipelineOrder:
        fileName = '/groups/lightsheet/lightsheet/home/ackermand/Lightsheet-Processing-Pipeline/Compiled_Functions/sampleInput_'+ currentStep +'.json';
        json_data = json.load(open(fileName))
        pipelineSteps.append({
           'stepName': currentStep,
           'inputJson': json.dumps(json_data, indent=4, separators=(',', ': '))
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
                jsonifiedText = json.loads(text)
                numTimePoints = math.ceil(1+(jsonifiedText["timepoints"]["end"] - jsonifiedText["timepoints"]["start"])/jsonifiedText["timepoints"]["every"])
                allSelectedStepNames = allSelectedStepNames+currentStep+", "
                allSelectedTimePoints = allSelectedTimePoints+str(numTimePoints)+", "
                step+=1
                #allSelectedTimePoints.append(numTimePoints)
                #allSelectedScriptNames.append(fileName)
        
        davidTest_json_data["args"].extend(("-allSelectedStepNames",allSelectedStepNames[0:-2]))
        davidTest_json_data["args"].extend(("-allSelectedTimePoints",allSelectedTimePoints[0:-2]))
        print(json.dumps(davidTest_json_data))
        r = requests.post('http://10.36.13.18:9000/api/rest-v2/async-services/lightsheetProcessing',
                          headers=headers,
                          data=json.dumps(davidTest_json_data))
                
       # print(json.dumps(json_data, indent=4, separators=(',',': ')))
       
    
    return render_template('index.html',
                           title='Home',
                           pipelineSteps=pipelineSteps)

@app.route('/db_test')
def db_test_page():
    connection = MongoClient()
    db = connection.jacs
    serviceHistory = list(list(db.jacsServiceHistory.find({"name": "lightsheetProcessing"},{"_id":0,"creationDate":1,"args":1}))) #get all that have name lightsheetProcessing (so it is the parent job), dont show the id, show creationDate and args
    #online_users = list(mongo.db.collection_names())
    for dictionary in serviceHistory: #convert date to nicer string
        dictionary.update((k,str(v)) for k, v in dictionary.items() if k=="creationDate")

    print(serviceHistory)
    return render_template('db_test_page.html', 
                            serviceHistory=serviceHistory)

        
        

