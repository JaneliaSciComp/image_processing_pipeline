from flask import Flask
from flask_mongoengine import MongoEngine
from flask_admin import Admin

app = Flask(__name__) #app variable, an object of class FLask
app.secret_key = 'this_is_secret_key'
db = MongoEngine(app)
admin=Admin(app)

from app import views, models #app package from which views will be imported
