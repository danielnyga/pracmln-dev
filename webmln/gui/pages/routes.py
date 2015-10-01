import os
from os.path import expanduser
import logging
from logging import FileHandler
import tempfile
from webmln.gui.app import mlnApp, app


def ulogger(name): return logging.getLogger('userstats')

#equivalent to register_routes in routes.py in local app
def register_routes(mlnapp=None):
    print 'Registering MLN routes...'
    mlnApp.app = app
    mlnApp.app.config['MLN_STATIC_PATH'] = os.path.join(mlnApp.app.root_path, 'build')

    # settings for fileupload and logging
    home = expanduser("~")
    mlnApp.app.config['ALLOWED_EXTENSIONS'] = set(['mln','db','pracmln','emln'])
    # mlnApp.app.config['UPLOAD_FOLDER'] = os.path.join(home, 'mlnfiles')
    mlnApp.app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
    mlnApp.app.config['EXAMPLES_FOLDER'] = os.path.join(mlnApp.app.root_path, '..', '..', 'examples')
    mlnApp.app.config['MLN_ROOT_PATH'] = os.path.join(mlnApp.app.root_path, '..', '..')

    mlnApp.app.config['LOG_FOLDER'] = os.path.join(mlnApp.app.root_path, 'log')
    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
        os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))
    mlnApp.app.secret_key = 'so secret!'

    # separate logger for user statistics
    ulog = logging.getLogger('userstats')
    ulog.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s,")
    filelogger = FileHandler(os.path.join(mlnApp.app.config['LOG_FOLDER'], "userstats.json"))
    filelogger.setFormatter(formatter)
    ulog.addHandler(filelogger)

    from webmln.gui.pages import mlnSpec
    from webmln.gui.pages import learning
    from webmln.gui.pages import inference
    from webmln.gui.pages import views
    from webmln.gui.pages import fileupload
    from webmln.gui.pages import utils
