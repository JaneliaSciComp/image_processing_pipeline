# Lightsheet Pipeline Flask App

This repo contains a python flask application to configure step parameters for pipeline jobs.

Make sure, your python is version 3.5 or higher and your pip is using this correct python:

```bash
$ python --version
$ pip --version
$ which python
$ which pip
```

Create a virtualenv environment, here the environment is called 'env':

```bash
$ virtualenv env --no-site-packages
```

or better

```bash
$ virtualenv --no-site-packages -p [path to your python] env
```

If you are on a Mac, use venv instead of virtualenv, because mathplotlib needs a framework build of Python

```bash
$ python -m venv env
```

Activate the environment:

```bash
$ source env/bin/activate
```

Install the requirements:

```bash
$ pip install -r requirements.txt
```

In Ubuntu, I had trouble doing that, because of issues with permissions when accessing some python libs in my HOME directory. I resolved that by pointing the HOME environment variable to another folder:

```bash
$ export HOME=/opt/home
$ sudo chown [your user name]:[your group] /opt/home
```

Then create the settings.py file by copying settings.py.template and filling in the missing values. Please also make sure, that the given host IP address in run.py is correct and change it to

```bash
127.0.0.1
```

which is localhost, if necessary.

With

```bash
$ python run.py
```

you should be able to run the Flask application.

If you're done with coding, you can deactivate the environment with the command

```bash
$ deactivate
```

### Deployment

If you haven't done so, in the folder where package.json is located, install the npm packages to install flightplan:

```bash
$ npm install
```

Make changes to target and config in flightplan.js as necessary. Then use flightplan to create a new version entry in package.json and as a git commit with

```bash
$ fly version:local [ patch | minor | major ]
```

Finally, deploy the application with

```bash
$ fly deploy:production
```

--------

Stop and start lightsheet services:

```bash
$ sudo systemctl stop lightsheet
$ sudo systemctl stop lightsheet
```

Set owner and permissions socket file:

```bash
$ sudo chown kazimiersa:nginx lightsheet.sock
$ sudo sudo chmod g+w lightsheet.sock
```