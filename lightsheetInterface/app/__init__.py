import os
import dateutil, socket, json
import config

from flask import Flask
from flask_debugtoolbar import DebugToolbarExtension
from flask_login import LoginManager, current_user
from flask_mongoengine import MongoEngine
from datetime import datetime


def _create_ui_app(cfg):
    ui_app = Flask(__name__)  # app variable, an object of class FLask
    ui_app.config.from_object(cfg)
    env_config_file = _get_env_config_file()
    if env_config_file:
        print(f'Read env from {env_config_file}', flush=True)
        ui_app.config.from_pyfile(env_config_file)

    app_root = ui_app.config.get('APPLICATION_ROOT', '/')
    print(f'Application root: {app_root}')
    return ui_app


def _create_db_config(ui_app):
    host = ui_app.config.get('MONGODB_HOST', 'localhost:27017')
    db = ui_app.config.get('MONGODB_DB', 'lightsheet')
    authentication_source = ui_app.config.get('MONGODB_AUTHENTICATION_SOURCE', '')
    replicaset = ui_app.config.get('MONGODB_REPLICASET', '')
    username = ui_app.config.get('MONGODB_USERNAME','')
    password = ui_app.config.get('MONGODB_PASSWORD','')
    return {
        'host': host,
        'db': db,
        'username': username,
        'password': password,
        'replicaset': replicaset,
        'authentication_source': authentication_source,
    }


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

db_config = _create_db_config(app)
app.config['MONGODB_SETTINGS'] = db_config
db = MongoEngine(app)
toolbar = DebugToolbarExtension(app)

from app import views, models
from app.models import PipelineInstance

admin = models.create_admin(app)


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=6, separators=(',', ':'))


app.jinja_env.filters['tojson_pretty'] = to_pretty_json


# Define some global template variables
@app.context_processor
def add_global_variables():
    is_admin = current_user.is_authenticated and current_user.username in app.config.get('ADMINS', [])
    return dict(date_now=datetime.now(),
                is_admin=is_admin)


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
def _jinja2_filter_datetime_short(date, fmt=None):
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
