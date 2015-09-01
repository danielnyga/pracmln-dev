import json
import logging
import os
from pracmln.mln.methods import InferenceMethods, LearningMethods
from pracmln.praclog import logger
from utils import getFileContent, ensure_mln_session, initialize, get_example_files
from urlparse import urlparse
from flask import render_template, send_from_directory, request, session, jsonify
import time
from werkzeug.utils import redirect
from webmln.gui.app import mlnApp

log = logger(__name__)


@mlnApp.app.after_request
def remove_if_invalid(response):
    log = logging.getLogger(__name__)
    if "__invalidate__" in session:
        response.delete_cookie(mlnApp.app.session_cookie_name)
        mln_session = mlnApp.session_store[session]
        if mln_session is not None:
            log.info('removed mln session %s' % mln_session.id.encode('base-64'))
            mlnApp.session_store.remove(session)
        session.clear()
    return response


@mlnApp.app.route('/mln/')
def mln():
    ensure_mln_session(session)
    return render_template('learn.html', **locals())


@mlnApp.app.route('/mln/log')
def mlnlog():
    return mlnlog_('null')


@mlnApp.app.route('/mln/home/')
def _mln():
    error = ''
    host_url = urlparse(request.host_url).hostname
    container_name = ''
    ensure_mln_session(session)
    time.sleep(2)
    return redirect('/mln/')


@mlnApp.app.route('/mln/_destroy_session', methods=['POST', 'OPTIONS'])
def destroy():
    log = logging.getLogger(__name__)
    mln_session = mlnApp.session_store[session]
    if mln_session is None: return ''
    log.info('invalidating session %s' % mln_session.id.encode('base-64'))
    session["__invalidate__"] = True
    return mln_session.id.encode('base-64')


@mlnApp.app.route('/mln/static/<path:filename>')
def download_static(filename):
    return send_from_directory(mlnApp.app.config['MLN_STATIC_PATH'], filename)


@mlnApp.app.route('/mln/doc/<path:filename>')
def download_docs(filename):
    return send_from_directory(os.path.join(mlnApp.app.config['MLN_ROOT_PATH'], 'doc'), filename)


@mlnApp.app.route('/mln/_get_filecontent', methods=['POST'])
def load_filecontent():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    filename = data['filename']
    text = ''

    if os.path.exists(os.path.join(mlnsession.xmplFolder, filename)):
        text = getFileContent(mlnsession.xmplFolder, filename)
    elif os.path.exists(os.path.join(mlnsession.xmplFolderLearning, filename)):
        text = getFileContent(mlnsession.xmplFolderLearning, filename)
    elif os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], filename)):
        text = getFileContent(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']), filename)

    return jsonify({'text': text})


# route for qooxdoo resources
@mlnApp.app.route('/mln/resource/<path:filename>')
def resource_file(filename):
    return redirect('/mln/static/resource/{}'.format(filename))


@mlnApp.app.route('/mln/save_edited_file', methods=['POST'])
def save_edited_file():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    fname = data['fname']
    newfname = data['newfname']
    fcontent = data['content']
    folder = data['folder']
    name = newfname or fname

    # if file exists in examples folder, do not update it but create new one in
    # UPLOAD_FOLDER with edited filename
    if os.path.exists(os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], folder, fname)):
        name = newfname or '_edited.'.join(fname.split('.'))

    # rename existing file with new filename or create/overwrite
    if os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], fname)) and newfname:
        os.rename(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], fname), os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], name))
    else:
        with open(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], name), 'w+') as f:
            f.write(fcontent)

    return jsonify({'fname': name})


@mlnApp.app.route('/mln/log/<filename>')
def mlnlog_(filename):
    if os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], filename)):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], filename)
    elif os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], '{}.json'.format(filename))):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], '{}.json'.format(filename))
    else:
        return render_template('log.html', **locals())



@mlnApp.app.route('/mln/_init', methods=['GET', 'OPTIONS'])
def init_options():
    log.info('init_options')
    mlnsession = ensure_mln_session(session)
    initialize()

    mlnfiles, dbfiles = get_example_files(mlnsession.xmplFolder)

    dirs = [x for x in os.listdir(mlnApp.app.config['EXAMPLES_FOLDER']) if
            os.path.isdir(
                os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], x))]

    inferconfig = mlnsession.inferconfig.config
    inferconfig.update({"method": InferenceMethods.name(mlnsession.inferconfig.config['method'])})

    lrnconfig = mlnsession.learnconfig.config
    lrnconfig.update({"method": LearningMethods.name(mlnsession.learnconfig.config['method'])})

    resinference = {'methods': sorted(InferenceMethods.names()),
           'config': inferconfig}
    reslearn = {'methods': sorted(LearningMethods.names()),
           'config': lrnconfig}

    return jsonify({"inference": resinference, "learning": reslearn, "mlnfiles": mlnfiles, "dbfiles": dbfiles, "examples": dirs})
