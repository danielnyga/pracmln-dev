import logging
import os
from webmln.mlninit import mlnApp
from flask import send_from_directory, render_template
from webmln.app import MLNSession
from werkzeug.utils import redirect


def ensure_mln_session(session):
    log = logging.getLogger(__name__)
    mln_session = mlnApp.session_store[session]
    if mln_session is None:
        session['id'] = os.urandom(24)
        prac_session = MLNSession(session)
        log.info('created new MLN session %s' % str(prac_session.id.encode(
            'base-64')))
        mlnApp.session_store.put(prac_session)
        initFileStorage()
    return prac_session

@mlnApp.app.route('/prac/log')
def praclog():
    return praclog_('null')

@mlnApp.app.route('/prac/log/<filename>')
def praclog_(filename):
    if os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], filename)):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], filename)
    elif os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'],
                                     '{}.json'.format(filename))):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], '{}.json'.format(filename))
    else:
        return render_template('logs.html', **locals())


def initFileStorage():
    if not os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']))

    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))

# route for qooxdoo resources
@mlnApp.app.route('/mln/resource/<path:filename>')
def resource_file(filename):
    return redirect('/mln/static/resource/{}'.format(filename))