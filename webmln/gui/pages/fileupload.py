import os
from flask import request, send_from_directory, jsonify, redirect
from werkzeug import secure_filename
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import initFileStorage


@mlnApp.app.route('/mln/uploads/<filedir>/<filename>')
def uploaded_file(filedir, filename):
    if not 'UPLOAD_FOLDER' in mlnApp.app.config:
        initFileStorage()
    return send_from_directory(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], filedir), filename)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in mlnApp.app.config['ALLOWED_EXTENSIONS']

@mlnApp.app.route('/mln/file_upload', methods=['GET', 'POST'])
def upload():
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        fpath = mlnApp.app.config['UPLOAD_FOLDER']
        if not os.path.exists(fpath):
            os.mkdir(fpath)
        file.save(os.path.join(fpath, filename))
    else:
        return 'File type not allowed. Allowed extensions: {}'.format(', '.join(mlnApp.app.config['ALLOWED_EXTENSIONS']))
    return ''


@mlnApp.app.route('/mln/saveMLN/', methods=['POST'])
def saveMLN():
    if not 'UPLOAD_FOLDER' in mlnApp.app.config:
        initFileStorage()
    data = request.get_json()
    MLNPATH = os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], 'mln')
    content = str(data['content'])
    fName = str(data['fName'])
    if '.' in fName and fName.rsplit('.', 1)[1] == 'mln':
        fullFileName = os.path.join(MLNPATH, fName)
    else:
        fullFileName = os.path.join(MLNPATH, "{}.mln".format(fName.rsplit('.', 1)[0]))

    if not os.path.exists(MLNPATH):
        os.mkdir(MLNPATH)    
    with open(fullFileName,'w') as f:
        f.write(content)

    return jsonify({'path': fullFileName})

