import collections
import os
import tempfile
from flask import jsonify, session
from fnmatch import fnmatch
from pracmln.mln.methods import LearningMethods, InferenceMethods
from pracmln.mln.util import out
from pracmln.praclog import logger
from pracmln.utils.latexmath2png import math2png
from pracmln.utils.project import MLNProject
from webmln.gui.app import mlnApp, MLNSession
from shutil import copyfile
import ntpath

FILEDIRS = {'mln': 'mln', 'pracmln': 'bin', 'db': 'db'}
GUI_SETTINGS = ['db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output', 'grammar', 'queries', 'emln']
DEFAULT_EXAMPLE = 'smokers'
DEFAULT_PROJECT = 'smokers.pracmln'

log = logger(__name__)


def ensure_mln_session(cursession):
    mln_session = mlnApp.session_store[cursession]
    if mln_session is None:
        cursession['id'] = os.urandom(24)
        mln_session = MLNSession(cursession)
        log.info('created new MLN session %s' % str(mln_session.id.encode('base-64')))
        mln_session.tmpsessionfolder = init_file_storage()
        log.info('created tempfolder %s' % mln_session.tmpsessionfolder)
        mln_session.projectinf = MLNProject.open(os.path.join(mln_session.tmpsessionfolder, DEFAULT_PROJECT))
        mln_session.projectlearn = MLNProject.open(os.path.join(mln_session.tmpsessionfolder, DEFAULT_PROJECT))
        mlnApp.session_store.put(mln_session)
    return mln_session


def init_file_storage():
    if not os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'])):
        os.mkdir(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']))
    dirname = tempfile.mkdtemp(prefix='webmln', dir=mlnApp.app.config['UPLOAD_FOLDER'])

    # copy project files from examples folder to tempdir so the user can edit them
    # without messing anything up in the examples folder
    for root, dirs, files in os.walk(mlnApp.app.config['EXAMPLES_FOLDER']):
        for file in files:
            if file.endswith('.pracmln'):
                copyfile(os.path.join(root, file), os.path.join(dirname,file))

    if not os.path.exists(os.path.join(mlnApp.app.config['LOG_FOLDER'])):
        os.mkdir(os.path.join(mlnApp.app.config['LOG_FOLDER']))

    return dirname


def convert(data):
    """
    Converts a dictionary's keys/values from unicode to string
    - data:    dictionary containing unicode keys and values
    - returns:  the converted dictionary
    """
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data


def change_example(task, project):
    log.info('change_example')
    mlnsession = ensure_mln_session(session)

    tmpfolder = os.path.join(mlnsession.tmpsessionfolder, project)
    if not os.path.exists(tmpfolder):
        return False

    if task == 'inference':
        mlnsession.projectinf = MLNProject.open(tmpfolder)
        dbfiles = mlnsession.projectinf.dbs.keys()
        mlnfiles = mlnsession.projectinf.mlns.keys()
    else:
        mlnsession.projectlearn = MLNProject.open(tmpfolder)
        dbfiles = mlnsession.projectlearn.dbs.keys()
        mlnfiles = mlnsession.projectlearn.mlns.keys()

    inferconfig = mlnsession.projectinf.queryconf.config.copy()
    inferconfig.update({"method": InferenceMethods.name(mlnsession.projectinf.queryconf.get("method", 'MC-SAT'))})
    lrnconfig = mlnsession.projectlearn.learnconf.config.copy()
    lrnconfig.update({"method": LearningMethods.name(mlnsession.projectlearn.learnconf.get("method", 'BPLL'))})

    res = {'dbs': dbfiles, 'mlns': mlnfiles,
           'lrnconfig': lrnconfig,
           'lrnmethods': sorted(LearningMethods.names()),
           'infconfig': inferconfig,
           'infmethods': sorted(InferenceMethods.names())}
    return jsonify(res)


def get_training_db_paths(pattern):
    """
    determine training databases(s)
    """
    mlnsession = ensure_mln_session(session)
    dbs = []
    local = False
    if pattern is not None and pattern.strip():
        fpath, pat = ntpath.split(pattern)
        if not os.path.exists(fpath):
            log.debug('%s does not exist. Searching for pattern %s in project %s...' % (fpath, pat, mlnsession.projectinf.name))
            local = True
            dbs = [db for db in mlnsession.projectinf.project.dbs if fnmatch(db, pattern)]
            if len(dbs) == 0:
                raise Exception("The pattern '%s' matches no files in your project %s" % (pat, mlnsession.projectinf.name))
        else:
            local = False
            patternpath = os.path.join(mlnsession.tmpsessionfolder, pattern)

            d, mask = os.path.split(os.path.abspath(patternpath))
            for fname in os.listdir(d):
                print fname
                if fnmatch(fname, mask):
                    dbs.append(os.path.join(d, fname))
            if len(dbs) == 0:
                raise Exception("The pattern '%s' matches no files in %s" % (pat, fpath))
        log.debug('loading training databases from pattern %s:' % pattern)
        for p in dbs: log.debug('  %s' % p)
    if not dbs:
        raise Exception("No training data given; A training database must be selected or a pattern must be specified")
    else: return local, dbs


def get_cond_prob_png(queries, db, filename='cond_prob', filedir='/tmp'):
    declarations = r'''
    \DeclareMathOperator*{\argmin}{\arg\!\min}
    \DeclareMathOperator*{\argmax}{\arg\!\max}
    \newcommand{\Pcond}[1]{\ensuremath{P\left(\begin{array}{c|c}#1\end{array}\right)}}
    '''

    evidencelist = []
    evidencelist.extend([e if db.evidence[e] == 1.0 else '!'+e for e in db.evidence.keys() ])
    query    = r'''\\'''.join([r'''\text{{ {0} }} '''.format(q.replace('_', '\_')) for q in queries])
    evidence = r'''\\'''.join([r'''\text{{ {0} }} '''.format(e.replace('_', '\_')) for e in evidencelist])
    eq       = r'''\argmax \Pcond{{ \begin{{array}}{{c}}{0}\end{{array}} & \begin{{array}}{{c}}{1}\end{{array}} }}'''.format(query, evidence)

    return math2png(eq, filedir, declarations=[declarations], filename=filename, size=10)
