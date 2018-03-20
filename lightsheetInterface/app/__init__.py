from flask import Flask
from flask_cache import Cache
from flask_mongoengine import MongoEngine
from mongoengine import connect
from flask_admin import Admin
import dateutil

app = Flask(__name__) #app variable, an object of class FLask
app.secret_key = 'this_is_secret_key'

# config settings
app.config['CACHE_TYPE'] = 'simple'
app.cache = Cache(app)

# db settings
admin=Admin(app)
app.config['MONGODB_SETTINGS'] = {
    'db': 'lightsheet-config',
    'host': '10.40.3.155',
    'port': 27017
}
db = MongoEngine(app)

# dev settings
app.config['TEMPLATES_AUTO_RELOAD'] = True

from app import views, models #app package from which views will be imported

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    date = dateutil.parser.parse(date)
    native = date.replace(tzinfo=None)

    format= "%Y-%m-%d at %H:%M:%S"
    return native.strftime(format)