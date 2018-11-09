import sys, os
sys.path = sys.path + [os.path.dirname(__file__)]
from app import app as application

if __name__ == "__main__":
    application.run()