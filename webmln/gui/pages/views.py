import json
import logging
import os
import shutil
import imp
from pracmln import mlnpath
from pracmln.mln.methods import InferenceMethods, LearningMethods
from pracmln.mln.util import out, stop, colorize
from pracmln.praclog import logger
from utils import ensure_mln_session, convert
from urlparse import urlparse
from flask import render_template, send_from_directory, request, session, \
    jsonify, \
    url_for, current_app, make_response
import time
from werkzeug.utils import redirect
from webmln.gui.app import mlnApp
from webmln.gui.pages.routes import ulogger


log = logger(__name__)
ulog = ulogger('userstats')


@mlnApp.app.route('/mln/static/<path:filename>')
def download_mln_static(filename):
    return send_from_directory(mlnApp.app.config['MLN_STATIC_PATH'], filename)


@mlnApp.app.route('/mln/doc/<path:filename>')
def download_mln_docs(filename):
    return send_from_directory(
        os.path.join(mlnApp.app.config['MLN_ROOT_PATH'], 'doc'), filename)


@mlnApp.app.route('/mln/')
def mln():
    mlnsession = ensure_mln_session(session)

    # # experimental
    # response = make_response(render_template('welcome.html', **locals()))
    # response.set_cookie('session_id', value=mlnsession.id)
    # return response
    # # get cookie in request with request.cookies.get('session_id')

    # render learn.html instead for loading page without welcome screen
    return render_template('welcome.html', **locals())


@mlnApp.app.route('/mln/home/')
def _mln():
    error = ''
    host_url = urlparse(request.host_url).hostname
    container_name = ''
    ensure_mln_session(session)
    time.sleep(2)
    return redirect('/mln/webmln')


@mlnApp.app.route('/mln/webmln', methods=['GET', 'POST'])
def webmln():
    ensure_mln_session(session)
    return render_template('learn.html', **locals())


@mlnApp.app.after_request
def remove_if_invalid(response):
    log = logging.getLogger(__name__)
    if "__invalidate__" in session:
        response.delete_cookie(mlnApp.app.session_cookie_name)
        mln_session = mlnApp.session_store[session]
        if mln_session is not None:
            log.info(
                'removed mln session %s' % mln_session.id.encode('base-64'))
            mlnApp.session_store.remove(session)
        session.clear()
    return response


@mlnApp.app.route('/mln/_destroy_session', methods=['POST', 'OPTIONS'])
def destroy():
    mln_session = mlnApp.session_store[session]
    if mln_session is None: return ''
    if os.path.exists(mln_session.tmpsessionfolder):
        log.info('removing temporary folder %s' % mln_session.tmpsessionfolder)
        shutil.rmtree(mln_session.tmpsessionfolder)
    log.info('invalidating session %s' % mln_session.id.encode('base-64'))
    session["__invalidate__"] = True
    return mln_session.id.encode('base-64')


@mlnApp.app.route('/mln/menu', methods=['POST'])
def mln_menu():
    menu_left = []

    selection = "Options"
    choices = [('PracINFER', url_for('prac') + 'pracinfer')]

    menu_right = [
        ('CHOICES', (selection, choices))
    ]

    return jsonify(menu_left=menu_left, menu_right=menu_right)


@mlnApp.app.route('/mln/log')
def mlnlog():
    return mlnlog_('null')


@mlnApp.app.route('/mln/log/<filename>')
def mlnlog_(filename):
    if os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'], filename)):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'], filename)
    elif os.path.isfile(os.path.join(mlnApp.app.config['LOG_FOLDER'],
                                     '{}.json'.format(filename))):
        return send_from_directory(mlnApp.app.config['LOG_FOLDER'],
                                   '{}.json'.format(filename))
    else:
        return render_template('userstats.html', **locals())


@mlnApp.app.route('/mln/_user_stats', methods=['POST'])
def user_stats():
    data = convert(json.loads(request.get_data()))
    ip = data['ip'] if data['ip'] is not None else request.remote_addr
    stats = {}

    logstr = ("Wrote log entry:\n"
              "IP:\t\t{ip}\n"
              "Country:\t{country}\n"
              "Continent:\t{continent}\n"
              "Subdivisions:\t{subdivisions}\n"
              "Timezone:\t{timezone}\n"
              "Location:\t{location}\n"
              "Access Date:\t{date}\n"
              "Access Time:\t{time}")

    try:
        imp.find_module('geoip')
        from geoip import geolite2
        try:
            geolite = geolite2.lookup(ip)
            stats.update(geolite.to_dict())
            stats['subdivisions'] = ', '.join(
                stats['subdivisions'])  # prettify for log
        except AttributeError:
            logstr = ("Wrote log entry:\n"
                      "IP:\t\t\t\t{ip}\n"
                      "Access Date:\t{date}\n"
                      "Access Time:\t{time}")
        except ValueError:
            log.error('Not a valid ip address: {}'.format(ip))
        except KeyError:
            logstr = ("Wrote log entry:\n"
                      "IP:\t\t\t\t{ip}\n"
                      "Country:\t\t{country}\n"
                      "Continent:\t\t{continent}\n"
                      "Timezone:\t\t{timezone}\n"
                      "Location:\t\t{location}\n"
                      "Access Date:\t{date}\n"
                      "Access Time:\t{time}")
    except ImportError:
        print colorize(
            'geoip module was not found. Install by "sudo pip install python-geoip python-geoip-geolite2" if you want to request geoip information',
            (None, 'yellow', True), True)
    finally:
        stats.update({'ip': ip, 'date': data['date'], 'time': data['time']})
        ulog.info(json.dumps(stats))
        log.info(logstr.format(**stats))
        return ''


# route for qooxdoo resources
@mlnApp.app.route('/mln/resource/<path:filename>')
def resource_file(filename):
    return redirect('/mln/static/resource/{}'.format(filename))


@mlnApp.app.route('/mln/_get_filecontent', methods=['POST'])
def load_filecontent():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    filename = data['filename']
    proj = data.get('project', True)
    text = ''

    path = '{}:{}'.format(os.path.join(mlnsession.tmpsessionfolder, proj),
                          filename)
    if mlnpath(path).exists:
        text = mlnpath(path).content

    return jsonify({'text': text})


@mlnApp.app.route('/mln/save_edited_file', methods=['POST'])
def save_edited_file():
    mlnsession = ensure_mln_session(session)

    data = json.loads(request.get_data())
    fname = data['fname']
    rename = data['rename']
    newfname = data['newfname']
    fcontent = data['content']
    folder = data['folder']
    name = newfname if rename else fname

    # if file exists in examples folder, do not update it but create new one in
    # UPLOAD_FOLDER with edited filename (filename is edited to avoid confusion
    # with duplicate filenames in list)
    if os.path.exists(
            os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], folder, name)):
        splitted = name.split('.')
        name = "{}_edited.{}".format(''.join(splitted[:-1]), splitted[-1])

    # rename existing file with new filename or create/overwrite
    if os.path.exists(
            os.path.join(mlnsession.tmpsessionfolder, fname)) and rename:
        os.rename(os.path.join(mlnsession.tmpsessionfolder, fname),
                  os.path.join(mlnsession.tmpsessionfolder, name))
    else:
        with open(os.path.join(mlnsession.tmpsessionfolder, name), 'w+') as f:
            f.write(fcontent)

    return jsonify({'fname': name})


@mlnApp.app.route('/mln/_init', methods=['GET'])
def init_options():
    mlnsession = ensure_mln_session(session)

    mlnfiles = mlnsession.projectinf.mlns.keys()
    dbfiles = mlnsession.projectinf.dbs.keys()

    examples = sorted([y for y in os.listdir(mlnsession.tmpsessionfolder) if
                       os.path.isfile(os.path.join(mlnsession.tmpsessionfolder,
                                                   y)) and y.endswith(
                           '.pracmln')])
    inferconfig = mlnsession.projectinf.queryconf.config.copy()
    inferconfig.update({"method": InferenceMethods.name(
        mlnsession.projectinf.queryconf.get('method', 'MCSAT'))})

    lrnconfig = mlnsession.projectlearn.learnconf.config.copy()
    lrnconfig.update({"method": LearningMethods.name(
        mlnsession.projectlearn.learnconf.get('method', 'BPLL'))})

    resinference = {'methods': sorted(InferenceMethods.names()),
                    'config': inferconfig}
    reslearn = {'methods': sorted(LearningMethods.names()),
                'config': lrnconfig}

    return jsonify(
        {"inference": resinference, "learning": reslearn, "mlnfiles": mlnfiles,
         "dbfiles": dbfiles, "examples": examples})


@mlnApp.app.route('/mln/_get_project_list', methods=['GET'])
def get_projects():
    mlnsession = ensure_mln_session(session)
    projects = [y for y in os.listdir(mlnsession.tmpsessionfolder) if
                os.path.isfile(os.path.join(mlnsession.tmpsessionfolder,
                                            y)) and y.endswith('.pracmln')]
    return jsonify({"projects": projects})
