import os
import logging
from werkzeug.serving import run_simple
from pracmln import praclog
from webmln.gui.app import mlnApp

log = praclog.logger(__name__)


def init_app(app):

    from gui.pages.routes import register_routes
    # Load all views.py files to register @app.routes() with Flask
    register_routes()

    return app

init_app(mlnApp.app)


if __name__ == '__main__':

    logging.getLogger().setLevel(logging.DEBUG)
    if 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'deploy':
        log.debug('Running WEBMLN in server mode')

        # load config
        mlnApp.app.config.from_object('configmodule.DeploymentConfig')

        mlnApp.app.run(host='0.0.0.0',
                       threaded=True,
                       port=5002)
    elif 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'testing':
        log.debug('Running WEBMLN in testing mode')

        # load config
        mlnApp.app.config.from_object('configmodule.TestingConfig')

        mlnApp.app.run(host='0.0.0.0',
                       threaded=True,
                       port=5002)
    elif 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'old':
        log.debug('Running WEBMLN in server mode')

        # load config
        mlnApp.app.config.from_object('configmodule.Config')

        certpath = os.path.dirname(os.path.realpath(__file__))
        context = (os.path.join(certpath, 'default.crt'), os.path.join(certpath, 'default.key'))
        run_simple('0.0.0.0',
                   5002,
                   mlnApp.app,
                   threaded=True,
                   ssl_context=context)
    else:
        log.debug('Running WEBMLN in development mode')

        # load config
        mlnApp.app.config.from_object('configmodule.DevelopmentConfig')

        mlnApp.app.run(host='0.0.0.0',
                       threaded=True,
                       port=5002)
