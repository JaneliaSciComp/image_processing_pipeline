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
# 'mongodb://mongodb4:27029,mongodb4:27030,mongodb4:27031/lightsheet?replicaSet=rsLightsheet&authSource=lightsheet'
MONGODB_HOST = 'mongodb://localhost:27017'
MONGODB_DB = 'lightsheet'
MONGODB_USERNAME = ''
MONGODB_PASSWORD = ''

UPLOAD_FOLDER = '/opt/projects/lightsheet/upload'

# Production auth service: http://api.int.janelia.org:8030/authenticate
# Dev auth service: https://jacs-dev.int.janelia.org/SCSW/AuthenticationService/v1/authenticate
AUTH_SERVICE_URL = 'https://c13u09.int.janelia.org/SCSW/AuthenticationService/v1/authenticate'
JACS_ASYNC_URL = 'http://jacs-dev.int.janelia.org:9000/api/rest-v2'
JACS_SYNC_URL = 'http://jacs-dev.int.janelia.org:9090/api/rest-v2'
JACS_DASHBOARD_URL = 'http://c13u09.int.janelia.org:8080'

ADMINS = []
#'http://10.37.6.38:9000/api/rest-v2' #'http://jacs-dev.int.janelia.org:9000/api/rest-v2' #'http://jacs2.int.janelia.org:9000/api/rest-v2' 'http://10.37.6.38:9000/api/rest-v2' #
