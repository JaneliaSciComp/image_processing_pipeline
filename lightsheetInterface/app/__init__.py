import os
import dateutil, socket, json
import config

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import LoginManager
from flask_mongoengine import MongoEngine
from flask_admin import Admin
from datetime import datetime


def _create_ui_app(cfg):
    ui_app = Flask(__name__)  # app variable, an object of class FLask
    ui_app.config.from_object(cfg)
    env_config_file = _get_env_config_file()
    if env_config_file:
        ui_app.config.from_pyfile(env_config_file)
    return ui_app


def _create_login_manager(ui_app):
    ui_lm = LoginManager()
    ui_lm.init_app(ui_app)
    if app.config['LOGIN_PAGE']:
        ui_lm.login_view = app.config['LOGIN_PAGE']
    return ui_lm


def _get_env_config_file():
    env_var = 'LIGHTSHEET_INTERFACE_SETTINGS'
    if env_var in os.environ:
        env_config_file = os.environ.get(env_var)
        return env_config_file if os.path.isfile(env_config_file) else None
    else:
        return None

app = _create_ui_app(config)
login_manager = _create_login_manager(app)

admin = Admin(app)
db = MongoEngine(app)
toolbar = DebugToolbarExtension(app)

from app import views, models
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

@app.context_processor
def get_jacs_dashboard_url():
    return dict(jacs_dashboard_url=app.config.get('JACS_DASHBOARD_URL'))

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)

    format = "%Y-%m-%d at %H:%M:%S"
    return native.strftime(format)


@app.template_filter('strftime_short')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)

    format = "%Y-%m-%d_%H:%M:%S"
    return native.strftime(format)


@app.template_filter('trimend')
def trimstepname(paramName):
    return paramName.split('_', 1)[0]


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
