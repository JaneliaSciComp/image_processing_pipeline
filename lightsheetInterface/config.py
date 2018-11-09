DEBUG = False
SECRET_KEY = 'the_very_secret_key'
CACHE_TYPE = 'simple'
TEMPLATES_AUTO_RELOAD = True
DEBUG_TB_PANELS = ['flask_debugtoolbar.panels.versions.VersionDebugPanel',
                   'flask_debugtoolbar.panels.timer.TimerDebugPanel',
                   'flask_debugtoolbar.panels.headers.HeaderDebugPanel',
                   'flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel',
                   'flask_debugtoolbar.panels.template.TemplateDebugPanel',
                   'flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel',
                   'flask_debugtoolbar.panels.logger.LoggingPanel',
                   'flask_debugtoolbar.panels.profiler.ProfilerDebugPanel']
DEBUG_TB_INTERCEPT_REDIRECTS = False
DEBUG_TB_MONGO = {
    'SHOW_STACKTRACES': True,
    'HIDE_FLASK_FROM_STACKTRACES': True
}

LOGIN_PAGE = '.login_form'

# These settings are needed exactly like this by flask mongo engine
# The host should always be mongodb://<hostname>:<port>/
# For localhost use 'mongodb://localhost:27017/lightsheet'
# For a replica set use something like:
# 'mongodb://mongodb4:27029,mongodb4:27030,mongodb4:27031/?replicaSet=rsLightsheet&authSource=lightsheet'
MONGODB_HOST = 'mongodb://localhost:27017/lightsheet'
MONGODB_USERNAME = ''
MONGODB_PASSWORD = ''

UPLOAD_FOLDER = '/groups/lightsheet/lightsheet/home/ackermand/upload'  # '/opt/projects/lightsheet/upload'

# Production auth service: http://api.int.janelia.org:8030/authenticate
# Dev auth service: https://jacs-dev.int.janelia.org/SCSW/AuthenticationService/v1/authenticate
AUTH_SERVICE_URL = 'https://jacs-dev.int.janelia.org/SCSW/AuthenticationService/v1/authenticate'
