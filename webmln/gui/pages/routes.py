import os
import logging
from webmln.gui.app import mlnApp, app


def ulogger(): return logging.getLogger('userstats')


def register_routes():
    print 'Registering MLN routes...'
    mlnApp.app = app

    mlnApp.app.config['LOG_FOLDER'] = os.path.join(mlnApp.app.root_path, 'log')
    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
        os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))

    # separate logger for user statistics
    root_logger = logging.getLogger('userstats')
    handler = logging.FileHandler(os.path.join(
        mlnApp.app.config['LOG_FOLDER'], "userstats.json"))
    formatter = logging.Formatter("%(message)s,")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    from webmln.gui.pages import mlnSpec
    from webmln.gui.pages import learning
    from webmln.gui.pages import inference
    from webmln.gui.pages import views
    from webmln.gui.pages import fileupload
    from webmln.gui.pages import utils
