from flask import Flask
#from flask_pymongo import PyMongo

app = Flask(__name__) #app variable, an object of class FLask
#mongo = PyMongo(app)

from app import views #app package from which views will be imported
