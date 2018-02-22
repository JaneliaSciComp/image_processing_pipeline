# Lightsheet Pipeline Flask App

This repo contains a python flask application to configure step parameters for pipeline jobs.

Make sure, your python is version 3.5 or higher and your pip is using this correct python:

`$ python --version`

`$ pip --version`

Create a virtualenv environment, here the environment is called 'env':

`$ virtualenv env --no-site-packages`

Activate the environment:

`$ source env/bin/activate`

Install the requirements:

`$ pip install -r requirements.txt`

In Ubuntu, I had trouble doing that, because of issues with permissions when accessing some python libs in my HOME directory. I resolved that by pointing the HOME environment variable to another folder:

`$ export HOME=/opt/home`

`$ sudo chown [your user name]:[your group] /opt/home`

Then create the settings.py file by copying settings.py.template and filling in the missing values. Please also make sure, that the given host IP address in run.py is correct and change it to

`127.0.0.1`

which is localhost, if necessary.

With

`$ python run.py`

you should be able to run the Flask application.

If you're done with coding, you can deactivate the environment with the command

`$ deactivate`