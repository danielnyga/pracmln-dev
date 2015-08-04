from StringIO import StringIO
from webmln.mlninit import mlnApp
import os
from os.path import expanduser
import logging
from logging import FileHandler

def register_routes(mlnapp=None):
    print 'Registering MLN routes...'
    from webmln.app import app
    mlnApp.app = app
    mlnApp.app.config['MLN_STATIC_PATH'] = os.path.join(mlnApp.app.root_path,
                                                      'build')

    # settings for fileupload and logging
    home = expanduser("~")
    mlnApp.app.config['ALLOWED_EXTENSIONS'] = set(['mln','db','pracmln'])
    mlnApp.app.config['UPLOAD_FOLDER'] = os.path.join(home, 'mlnfiles')
    mlnApp.app.config['EXAMPLES_FOLDER'] = os.path.join(mlnApp.app.root_path, '..', '..', 'examples')

    mlnApp.app.config['LOG_FOLDER'] = os.path.join(mlnApp.app.root_path, 'log')
    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))
    mlnApp.app.secret_key = 'so secret!'

    # separate logger for user statistics
    ulog = logging.getLogger('userstats')
    ulog.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s,")
    filelogger = FileHandler(os.path.join(mlnApp.app.config['LOG_FOLDER'], "logs.json"))
    filelogger.setFormatter(formatter)
    ulog.addHandler(filelogger)

    from webmln.pages import mlnSpec
    from webmln.pages import learning
    from webmln.pages import views
    from webmln.pages import utils
