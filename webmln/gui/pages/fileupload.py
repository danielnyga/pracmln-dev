import os
from flask import request, send_from_directory, session, jsonify
from werkzeug import secure_filename
from pracmln import mlnpath
from pracmln.mln.util import out
from pracmln.praclog import logger
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import ensure_mln_session


log = logger(__name__)


@mlnApp.app.route('/mln/uploads/<path:path>')
def uploaded_file(path):
    mlnsession = ensure_mln_session(session)
    return mlnpath('{}/{}'.format(mlnsession.tmpsessionfolder, path)).content


@mlnApp.app.route('/mln/projects/<path:path>')
def download_proj(path):
    mlnsession = ensure_mln_session(session)
    return send_from_directory(mlnsession.tmpsessionfolder, path)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in mlnApp.app.config['ALLOWED_EXTENSIONS']


@mlnApp.app.route('/mln/file_upload', methods=['GET', 'POST'])
def upload():
    mlnsession = ensure_mln_session(session)
    tmpfile = request.files['file']
    fcontent = tmpfile.read()
    source = request.form['SOURCE_PARAM'].encode('utf8').split('x')

    if tmpfile and allowed_file(tmpfile.filename):
        filename = secure_filename(tmpfile.filename)

        p = mlnsession.projectinf if source[0] == 'INF' else mlnsession.projectlearn

        if 'MLN' == source[1]:
            p.add_mln(filename, fcontent)
        elif 'DB' == source[1]:
            p.add_db(filename, fcontent)
        elif 'EMLN' == source[1]:
            p.add_emln(filename, fcontent)
        else:
            log.error('{} is not a valid file storage in project'.format(source[1]))
            return '{} is not a valid file storage in project'.format(source[1])

        p.save(mlnsession.tmpsessionfolder)
        log.info('added file {} to project {}'.format(filename, p.name))
    else:
        return 'File type not allowed. Allowed extensions: {}'.format(', '.join(mlnApp.app.config['ALLOWED_EXTENSIONS']))
    return ''


@mlnApp.app.route('/mln/proj_upload', methods=['GET', 'POST'])
def uploadProj():
    mlnsession = ensure_mln_session(session)
    tmpfile = request.files['file']

    if tmpfile and allowed_file(tmpfile.filename):
        filename = secure_filename(tmpfile.filename)
        tmpfile.save(os.path.join(mlnsession.tmpsessionfolder, filename))
    else:
        return 'File type not allowed. Allowed extensions: {}'.format(', '.join(mlnApp.app.config['ALLOWED_EXTENSIONS']))
    return ''