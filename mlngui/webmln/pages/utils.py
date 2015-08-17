from StringIO import StringIO
import json
import logging
import os
import pickle
from webmln.mlninit import mlnApp
from flask import send_from_directory, render_template, jsonify, session
from webmln.app import MLNSession
import re
from multiprocessing.queues import Queue
import sys
from werkzeug.utils import redirect
from pracmln.mln.methods import InferenceMethods, LearningMethods
from fnmatch import fnmatch


FILEDIRS = {'mln':'mln', 'pracmln':'bin', 'db':'db'}
LEARN_CONFIG_PATTERN = '{}.learn.conf'
QUERY_CONFIG_PATTERN = '{}.query.conf'
GLOBAL_CONFIG_FILENAME = '.pracmln.conf'
GUI_SETTINGS = ['db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output', 'grammar', 'queries', 'emln']
DEFAULT_EXAMPLE = 'smokers'

INFERENCE_METHODS = InferenceMethods.names()
LEARNING_METHODS = sorted(LearningMethods.names())

# separate logger for user statistics
stream = StringIO()
handler = logging.StreamHandler(stream)
# sformatter = logging.Formatter("%(message)s\n")
sformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(sformatter)
log = logging.getLogger('streamlog')
log.setLevel(logging.INFO)
log.addHandler(handler)

class StdoutQueue(Queue):
    def __init__(self,*args,**kwargs):
        Queue.__init__(self,*args,**kwargs)

    def write(self,msg):
        self.put(msg)

    def flush(self):
        sys.__stdout__.flush()

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

def initFileStorage():
    if not os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']))

    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
       os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))


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


def initialize():
    log.info('initialize')
    mlnsession = ensure_mln_session(session)
    mlnsession.params = ''

    confignames = ["mlnquery.config.dat", "query.config.dat"]
    settings = {}
    for filename in confignames:
        configname = os.path.join(mlnsession.xmplFolder, filename)
        if os.path.exists(configname):
            try:
                settings = pickle.loads("\n".join(map(lambda x: x.strip(
                    "\r\n"), file(configname, "r").readlines())))
            except:
                log.info('Could not load file {}'.format(configname))
            break

    settingsL = {}
    configname = os.path.join(mlnsession.xmplFolder, "learnweights.config.dat")
    if os.path.exists(configname):
        try:
            settingsL = pickle.loads("\n".join(map(lambda x: x.strip(
                "\r\n"), file(configname, "r").readlines())))
        except:
            log.info('Could not load file {}'.format(configname))

    mlnsession.settings = settings
    mlnsession.settingsL = settingsL


def dump(path, config):
    with open(path, 'w+') as cf:
        json.dump(config, cf)


def change_example(task, folder):
    mlnsession = ensure_mln_session(session)

    if task == 'inference':
        mlnsession.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], folder)
        mlnFiles, dbs = getExampleFiles(mlnsession.xmplFolder)
    else:
        mlnsession.xmplFolderLearning = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], folder)
        mlnFiles, dbs = getExampleFiles(mlnsession.xmplFolderLearning)
    userMLNFiles, userDBS = getExampleFiles(os.path.join('/tmp', 'tempupload'))
    res = {'dbs': dbs + userDBS, 'mlns': mlnFiles + userMLNFiles}
    return jsonify( res )



def getExampleFiles(path):
    mlnFiles = []
    dbFiles = []

    if os.path.exists(path):
        for filename in os.listdir(path):
            if fnmatch(filename, '*.mln'):
                mlnFiles.append(filename)
            if fnmatch(filename, '*.db') or fnmatch(filename, '*.blogdb'):
                dbFiles.append(filename)

    mlnFiles.sort()
    dbFiles.sort()

    return mlnFiles, dbFiles


def get_training_db_paths(pattern):
    '''
    determine training databases(s)
    '''
    mlnsession = ensure_mln_session(session)
    if pattern is not None and pattern.strip():
        dbs = []
        patternpath = os.path.join(mlnsession.xmplFolderLearning, pattern)
        d, mask = os.path.split(os.path.abspath(patternpath))
        for fname in os.listdir(d):
            if fnmatch(fname, mask):
                dbs.append(os.path.join(d, fname))
        if len(dbs) == 0:
            raise Exception("The pattern '%s' matches no files in %s" % (pattern, mlnsession.xmplFolderLearning))
        log.info('loading training databases from pattern %s:')
        for p in dbs: log.info('  %s' % p)
    if not dbs:
        raise Exception("No training data given; A training database must be selected or a pattern must be specified")
    else: return dbs