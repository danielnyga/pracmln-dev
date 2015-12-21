import logging
from webmln.gui.app import mlnApp
from werkzeug.serving import run_simple
from OpenSSL import SSL
import os


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
    logging.getLogger().setLevel(logging.INFO)
    if 'PRAC_SERVER' in os.environ and os.environ['PRAC_SERVER'] == 'true':
        context = SSL.Context(SSL.SSLv23_METHOD)
        context.use_privatekey_file(os.path.join('../../', 'default.key'))
        context.use_certificate_file(os.path.join('../../', 'default.crt'))
        run_simple('0.0.0.0', 5002, mlnApp.app, ssl_context=context)
    else:
        mlnApp.app.run(host='0.0.0.0', port=5002, debug=True, threaded=True)

