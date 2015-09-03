import os
from flask import jsonify, session
import re
from fnmatch import fnmatch
from pracmln.mln.methods import LearningMethods, InferenceMethods
from pracmln.praclog import logger
from pracmln.utils.config import PRACMLNConfig, query_config_pattern, learn_config_pattern
from webmln.gui.app import mlnApp, MLNSession

FILEDIRS = {'mln': 'mln', 'pracmln': 'bin', 'db': 'db'}
GUI_SETTINGS = ['db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output', 'grammar', 'queries', 'emln']
DEFAULT_EXAMPLE = 'smokers'

log = logger(__name__)


def ensure_mln_session(session):
    mln_session = mlnApp.session_store[session]
    if mln_session is None:
        session['id'] = os.urandom(24)
        mln_session = MLNSession(session)
        mln_session.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
        mln_session.xmplFolderLearning = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
        log.info('created new MLN session %s' % str(mln_session.id.encode('base-64')))
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
        with open(os.path.join(fDir, fName), "r") as f:
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


def load_configurations():
    log.info('loading configurations...')
    mlnsession = ensure_mln_session(session)

    inferconfig = PRACMLNConfig(os.path.join(mlnsession.xmplFolder, query_config_pattern % mlnsession.xmplFolder.split('/')[-1]))
    learnconfig = PRACMLNConfig(os.path.join(mlnsession.xmplFolderLearning, learn_config_pattern % mlnsession.xmplFolderLearning.split('/')[-1]))

    mlnsession.inferconfig = inferconfig
    mlnsession.learnconfig = learnconfig


def change_example(task, folder):
    log.info('change_example')
    mlnsession = ensure_mln_session(session)
    f = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], folder)
    if task == 'inference':
        mlnsession.xmplFolder = f
    else:
        mlnsession.xmplFolderLearning = f

    load_configurations()

    mlnfiles, dbs = get_example_files(f)
    usermlnfiles, userdbs = get_example_files(mlnApp.app.config['UPLOAD_FOLDER'])

    inferconfig = mlnsession.inferconfig.config.copy()
    inferconfig.update({"method": InferenceMethods.name(mlnsession.inferconfig.config['method'])})

    lrnconfig = mlnsession.learnconfig.config.copy()
    lrnconfig.update({"method": LearningMethods.name(mlnsession.learnconfig.config['method'])})

    res = {'dbs': dbs + userdbs, 'mlns': mlnfiles + usermlnfiles,
           'lrnconfig': lrnconfig,
           'lrnmethods': sorted(LearningMethods.names()),
           'infconfig': inferconfig,
           'infmethods': sorted(InferenceMethods.names())}
    return jsonify(res)


def get_example_files(path):
    mlnfiles = []
    dbfiles = []

    if os.path.exists(path):
        for filename in os.listdir(path):
            if fnmatch(filename, '*.mln'):
                mlnfiles.append(filename)
            if fnmatch(filename, '*.db') or fnmatch(filename, '*.blogdb'):
                dbfiles.append(filename)

    mlnfiles.sort()
    dbfiles.sort()

    return mlnfiles, dbfiles


def get_training_db_paths(pattern):
    """
    determine training databases(s)
    """
    mlnsession = ensure_mln_session(session)
    dbs = []
    if pattern is not None and pattern.strip():
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
