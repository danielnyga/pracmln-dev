import logging
import os
from webmln.mlninit import mlnApp
from flask import send_from_directory, render_template
from webmln.app import MLNSession
import re
from werkzeug.utils import redirect

FILEDIRS = {'mln':'mln', 'pracmln':'bin', 'db':'db'}
LEARN_CONFIG_PATTERN = '{}.learn.conf'
QUERY_CONFIG_PATTERN = '{}.query.conf'
GLOBAL_CONFIG_FILENAME = '.pracmln.conf'
GUI_SETTINGS = ['db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output', 'grammar', 'queries', 'emln']
DEFAULT_EXAMPLE = 'smokers'


def ensure_mln_session(session):
    log = logging.getLogger(__name__)
    mln_session = mlnApp.session_store[session]
    if mln_session is None:
        session['id'] = os.urandom(24)
        mln_session = MLNSession(session)
        mln_session.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
        log.info('created new MLN session %s' % str(mln_session.id.encode(
            'base-64')))
        mlnApp.session_store.put(mln_session)
        initFileStorage()
    return mln_session

@mlnApp.app.route('/mln/log')
def mlnlog():
    return mlnlog_('null')

@mlnApp.app.route('/mln/log/<filename>')
def mlnlog_(filename):
    if os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], filename)):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], filename)
    elif os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'],
                                     '{}.json'.format(filename))):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], '{}.json'.format(filename))
    else:
        return render_template('log.html', **locals())


def initFileStorage():
    if not os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']))

    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))

# route for qooxdoo resources
@mlnApp.app.route('/mln/resource/<path:filename>')
def resource_file(filename):
    return redirect('/mln/static/resource/{}'.format(filename))


# returns content of given file, replaces includes by content of the included file
def getFileContent(fDir, fName):
    c = ''
    if os.path.isfile(os.path.join(fDir, fName)):
        with open (os.path.join(fDir, fName), "r") as f:
            c = f.readlines()

    content = ''
    for l in c:
        if '#include' in l:
            includefile = re.sub('#include ([\w,\s-]+\.[A-Za-z])', '\g<1>', l).strip()
            if os.path.isfile(os.path.join(fDir, includefile)):
                content += getFileContent(fDir, includefile)
            else:
                content += l
        else:
            content += l
    return content