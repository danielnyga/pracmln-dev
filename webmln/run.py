import pracmln
from webmln.gui.app import mlnApp
from werkzeug.serving import run_simple
import os

log = pracmln.praclog.logger(__name__)

def init_app(app):
    print 'initializing app...', app

    from gui.pages.routes import register_routes
    # Load all views.py files to register @app.routes() with Flask
    register_routes()
    
    # Initialize app config settings
    mlnApp.app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF checks while testing
    return

init_app(mlnApp.app)

if __name__ == '__main__':
    if 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'true':
        log.info('Running WEBMLN in server mode')
        certpath = os.path.dirname(os.path.realpath(__file__))
        context = (os.path.join(certpath, 'default.crt'), os.path.join(certpath, 'default.key'))
        run_simple('0.0.0.0', 5002, mlnApp.app, ssl_context=context)
    else:
        log.info('Running WEBMLN in development mode')
        mlnApp.app.run(host='0.0.0.0', port=5002, debug=True, threaded=True)

