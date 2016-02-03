import os
import logging
from pracmln import praclog
from webmln.gui.app import mlnApp
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

log = praclog.logger(__name__)


def init_app(app):

    from gui.pages.routes import register_routes
    # Load all views.py files to register @app.routes() with Flask
    register_routes()
    return

init_app(mlnApp.app)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    if 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'deploy':
        log.debug('Running WEBMLN in server mode')

        # load config
        mlnApp.app.config.from_object('configmodule.DeploymentConfig')

        http_server = HTTPServer(WSGIContainer(mlnApp.app))
        http_server.listen(5002)
        IOLoop.instance().start()
    elif 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'testing':
        log.debug('Running WEBMLN in testing mode')

        # load config
        mlnApp.app.config.from_object('configmodule.TestingConfig')

        mlnApp.app.run(host='0.0.0.0', port=5002)
    else:
        log.debug('Running WEBMLN in development mode')

        # load config
        mlnApp.app.config.from_object('configmodule.DevelopmentConfig')

        mlnApp.app.run(host='0.0.0.0', port=5002)
