import dateutil, ipdb, socket, json, logging
from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask_mongoengine import MongoEngine
from flask_admin import Admin
from datetime import datetime


app = Flask(__name__) #app variable, an object of class FLask
app.config.from_pyfile('lightsheet-config.cfg')

admin=Admin(app)
db = MongoEngine(app)
toolbar = DebugToolbarExtension(app)

from app import views, models #app package from which views will be imported
from app.models import PipelineInstance

def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=6, separators=(',', ':'))

app.jinja_env.filters['tojson_pretty'] = to_pretty_json

# Define some global template variables
@app.context_processor
def add_global_variables():
  return dict(date_now=datetime.now())

@app.context_processor
def add_machine_name():
  return dict(machine_name=socket.gethostname())

@app.context_processor
def get_configurations():
  configs = []
  instances = PipelineInstance.objects.all()
  for i in instances:
    configs.append(i)
  return dict(pConfig=configs)

@app.context_processor
def get_app_version():
  mpath = app.root_path.split('/')
  result = '/'.join(mpath[0:(len(mpath) - 1)]) + '/package.json'
  with open(result) as package_data:
    data = json.load(package_data)
    package_data.close()
    return dict(version=data['version'])

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)

    format= "%Y-%m-%d at %H:%M:%S"
    return native.strftime(format)

@app.template_filter('strftime_short')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)

    format= "%Y-%m-%d_%H:%M:%S"
    return native.strftime(format)

@app.template_filter('trimend')
def trimstepname(paramName):
    return paramName.split('_',1)[0]

@app.template_filter('show_attr')
def show_all_attrs(value):
    res = []
    for k in dir(value):
        res.append('%r %r<br/>' % (k, getattr(value, k)))
    return '\n'.join(res)

@app.template_filter('show_type')
def show_all_attrs(value):
    if type(value) is str:
        return 'string'
    elif type(value) is list:
        return 'list'
    return 'type'