import os
import tempfile
from webmln.gui.app import mlnApp


class Config(object):
    SECRET_KEY = 'so secret!'
    CSRF_ENABLED = True

    # settings for fileupload and logging
    ALLOWED_EXTENSIONS = {'mln', 'db', 'pracmln', 'emln'}
    MLN_STATIC_PATH = os.path.join(mlnApp.app.root_path, 'build')
    UPLOAD_FOLDER = tempfile.gettempdir()
    MLN_ROOT_PATH = os.path.join(mlnApp.app.root_path, '..', '..')
    EXAMPLES_FOLDER = os.path.join(mlnApp.app.root_path, '..', '..',
                                   'examples')


class DeploymentConfig(Config):
    DEBUG = False
    THREADED = False
    TESTING = False
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(Config):
    DEBUG = True
    THREADED = True
    TESTING = False
    WTF_CSRF_ENABLED = False


class TestingConfig(Config):
    DEBUG = False
    THREADED = False
    TESTING = True
    WTF_CSRF_ENABLED = False
