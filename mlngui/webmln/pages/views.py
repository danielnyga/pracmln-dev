import json
import logging
import os
from utils import getFileContent
from urlparse import urlparse
from webmln.mlninit import mlnApp
from flask import render_template, send_from_directory, request, session, \
    jsonify
import time
from webmln.pages.utils import ensure_mln_session
from werkzeug.utils import redirect

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
    # return render_template('mln.html', **locals()) // for openEASE integration
    return redirect('/mln/mlninfer')


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

@mlnApp.app.route('/mln/_get_filecontent', methods=['POST'])
def load_filecontent():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    filename = data['filename']
    text = ''

    if os.path.exists(os.path.join(mlnsession.xmplFolder, filename)):
        text = getFileContent(mlnsession.xmplFolder, filename)
    elif os.path.exists(os.path.join('/tmp', 'tempupload', filename)):
        text = getFileContent(os.path.join('/tmp', 'tempupload'), filename)

    return jsonify( {'text': text} )


# route for qooxdoo resources
@mlnApp.app.route('/mln/resource/<path:filename>')
def resource_file(filename):
    return redirect('/mln/static/resource/{}'.format(filename))


@mlnApp.app.route('/mln/log/<filename>')
def mlnlog_(filename):
    if os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], filename)):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], filename)
    elif os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'],
                                     '{}.json'.format(filename))):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], '{}.json'.format(filename))
    else:
        return render_template('log.html', **locals())

