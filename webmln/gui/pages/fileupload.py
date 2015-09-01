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


@mlnApp.app.route('/mln/saveMLN/', methods=['POST'])
def save_mln():
    if 'UPLOAD_FOLDER' not in mlnApp.app.config:
        initFileStorage()
    data = request.get_json()
    mlnpath = os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], 'mln')
    content = str(data['content'])
    fname = str(data['fName'])
    if '.' in fname and fname.rsplit('.', 1)[1] == 'mln':
        fullfilename = os.path.join(mlnpath, fname)
    else:
        fullfilename = os.path.join(mlnpath, "{}.mln".format(fname.rsplit('.', 1)[0]))

    if not os.path.exists(mlnpath):
        os.mkdir(mlnpath)
    with open(fullfilename, 'w') as f:
        f.write(content)

    return jsonify({'path': fullfilename})

