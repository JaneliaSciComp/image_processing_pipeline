from flask import Flask

app = Flask(__name__) #app variable, an object of class FLask

from app import views #app package from which views will be imported
