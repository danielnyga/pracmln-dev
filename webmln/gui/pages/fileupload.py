import os
from flask import request, send_from_directory, session
from werkzeug import secure_filename
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import ensure_mln_session

@mlnApp.app.route('/mln/uploads/<path:filename>')
def uploaded_file(filename):
    mlnsession = ensure_mln_session(session)
    return send_from_directory(mlnsession.tmpsessionfolder, filename)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in mlnApp.app.config['ALLOWED_EXTENSIONS']


@mlnApp.app.route('/mln/file_upload', methods=['GET', 'POST'])
def upload():
    mlnsession = ensure_mln_session(session)
    tmpfile = request.files['file']
    if tmpfile and allowed_file(tmpfile.filename):
        filename = secure_filename(tmpfile.filename)
        fpath = mlnsession.tmpsessionfolder
        if not os.path.exists(fpath):
            os.mkdir(fpath)
        tmpfile.save(os.path.join(fpath, filename))
    else:
        return 'File type not allowed. Allowed extensions: {}'.format(', '.join(mlnApp.app.config['ALLOWED_EXTENSIONS']))
    return ''
