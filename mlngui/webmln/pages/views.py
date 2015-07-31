import logging
from urlparse import urlparse
from webmln.mlninit import mlnApp
from flask import render_template, send_from_directory, request, session
import time
from webmln.pages.utils import ensure_mln_session
from werkzeug.utils import redirect
from webmln.pages.learning import initialize


@mlnApp.app.route('/mln/')
def mln():
    initialize()
    return render_template('learn.html', **locals())


@mlnApp.app.route('/mln/home/')
def _mln():
    log = logging.getLogger(__name__)
    error = ''
    host_url = urlparse(request.host_url).hostname
    container_name = ''
    ensure_mln_session(session)
    time.sleep(2)
    # return render_template('mln.html', **locals()) // for openEASE integration
    return redirect('/mln/mlninfer') 

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

@mlnApp.app.route('/mln/_destroy_session', methods=['POST', 'OPTIONS'])
def destroy():
    log = logging.getLogger(__name__)
    mln_session = mlnApp.session_store[session]
    if mln_session is None: return ''
    log.info('invalidating session %s' % mln_session.id.encode('base-64'))
    session["__invalidate__"] = True
    return mln_session.id.encode('base-64')