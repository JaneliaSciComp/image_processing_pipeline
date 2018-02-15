from models import Config, Step, Parameter
from mongoengine.queryset.visitor import Q

def testDatabaseStatus(db):
  # Issue the serverStatus command and print the results
  serverStatusResult=db.command("serverStatus")
  pprint(serverStatusResult)

def getType(param):
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
  return param


def buildConfigObject():
  steps = Step.objects.all().order_by('order')
  parameter = Parameter.objects.all()
  parameterNew = list(map(getType, parameter))

  config = {'steps': steps, 'parameter': parameterNew}
  # oneParam = Config.objects(Q(number2=None) & Q(number3=None) & (Q(type=None) | Q(type='')))
  # twoParam = Config.objects(Q(number2__ne=None) & Q(number3=None) & Q(type=None))
  # threeParam = Config.objects( Q(number1__ne=None) & Q(number2__ne=None) & Q(number3__ne=None) & (Q(type=None) | Q(type='')) )
  # steps = Config.objects(type='S')
  # config = {'onenum': oneParam, 'twonum': twoParam, 'threenum': threeParam, 'steps': steps}
  return config