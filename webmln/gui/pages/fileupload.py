import os
from flask import request, send_from_directory, jsonify, redirect
from werkzeug import secure_filename
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import initFileStorage


@mlnApp.app.route('/mln/uploads/<filedir>/<filename>')
def uploaded_file(filedir, filename):
    if 'UPLOAD_FOLDER' not in mlnApp.app.config:
        initFileStorage()
    return send_from_directory(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], filedir), filename)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in mlnApp.app.config['ALLOWED_EXTENSIONS']


@mlnApp.app.route('/mln/file_upload', methods=['GET', 'POST'])
def upload():
    tmpfile = request.files['file']
    if tmpfile and allowed_file(tmpfile.filename):
        filename = secure_filename(tmpfile.filename)
        fpath = mlnApp.app.config['UPLOAD_FOLDER']
        if not os.path.exists(fpath):
            os.mkdir(fpath)
        tmpfile.save(os.path.join(fpath, filename))
    else:
        return 'File type not allowed. Allowed extensions: {}'.format(', '.join(mlnApp.app.config['ALLOWED_EXTENSIONS']))
    return ''
