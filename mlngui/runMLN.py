from webmln.mlninit import mlnApp
import logging

def init_app(app):

    from webmln.pages.routes import register_routes
    # Load all views.py files to register @app.routes() with Flask
    register_routes()
    
    # Initialize app config settings
    mlnApp.app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF checks while testing

    return app


init_app(mlnApp.app)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    mlnApp.app.run(host='0.0.0.0', port=5002, debug=True, threaded=True)
