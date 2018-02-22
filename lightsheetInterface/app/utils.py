from app.models import AppConfig, Step, Parameter
from mongoengine.queryset.visitor import Q

def testDatabaseStatus(db):
  # Issue the serverStatus command and print the results
  serverStatusResult=db.command("serverStatus")
  pprint(serverStatusResult)

# Calculate properties of parameter based on its values (e.g. if number or text field has been filled in or which frequency / which range is selected)
def getType(parameter):
  frequent = []
  sometimes = []
  rare = []
  for param in parameter:
    if param.number1 != None:
      param.type = 'Number'
      if param.number2 == None:
        param.count = '1'
      elif param.number3 == None:
        param.count = '2'
      else:
        param.count = '3'
    else:
      param.type = 'Text'
      param.count = '1'

    if param.frequency == 'F':
      frequent.append(param)
    elif param.frequency == 'S':
      sometimes.append(param)
    elif param.frequency == 'R':
      rare.append(param)

  result = {'frequent': frequent, 'sometimes': sometimes, 'rare': rare}
  return result

def buildConfigObject():
  steps = Step.objects.all().order_by('order')
  parameter = Parameter.objects.all()
  paramNew = getType(parameter)

  config = {'steps': steps, 'parameter': paramNew}
  # oneParam = Config.objects(Q(number2=None) & Q(number3=None) & (Q(type=None) | Q(type='')))
  # twoParam = Config.objects(Q(number2__ne=None) & Q(number3=None) & Q(type=None))
  # threeParam = Config.objects( Q(number1__ne=None) & Q(number2__ne=None) & Q(number3__ne=None) & (Q(type=None) | Q(type='')) )
  # steps = Config.objects(type='S')
  # config = {'onenum': oneParam, 'twonum': twoParam, 'threenum': threeParam, 'steps': steps}
  return config

def writeToJSON(name, value):
  result = None;
  if value == None:
    result = "\"_ArrayType_\":\"double\",\"_ArraySize_\":[0,0],\"_ArrayData_\":null"
  elif isinstance(value, list):
    print(result)
  elif isinstance(value, (int, long, float, complex)):
    result = "\"" + name + "\":" + value,
  elif value in 'xyz':
    print(result)
  else:
    print(result)

  return result