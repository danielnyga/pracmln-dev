import collections
import os
import tempfile
from flask import jsonify, session
import re
from fnmatch import fnmatch
from pracmln.mln.methods import LearningMethods, InferenceMethods
from pracmln.mln.util import out
from pracmln.praclog import logger
from pracmln.utils.config import PRACMLNConfig, query_config_pattern, learn_config_pattern
from pracmln.utils.latexmath2png import math2png
from webmln.gui.app import mlnApp, MLNSession

FILEDIRS = {'mln': 'mln', 'pracmln': 'bin', 'db': 'db'}
GUI_SETTINGS = ['db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output', 'grammar', 'queries', 'emln']
DEFAULT_EXAMPLE = 'smokers'

log = logger(__name__)


def ensure_mln_session(cursession):
    mln_session = mlnApp.session_store[cursession]
    if mln_session is None:
        cursession['id'] = os.urandom(24)
        mln_session = MLNSession(cursession)
        mln_session.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
        mln_session.xmplFolderLearning = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
        log.info('created new MLN session %s' % str(mln_session.id.encode('base-64')))
        mln_session.tmpsessionfolder = init_file_storage()
        log.info('created tempfolder %s' % mln_session.tmpsessionfolder)
        mlnApp.session_store.put(mln_session)
    return mln_session


def init_file_storage():
    if not os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'])):
        os.mkdir(os.path.join(mlnApp.app.config['UPLOAD_FOLDER']))
    dirname = tempfile.mkdtemp(prefix='webmln', dir=mlnApp.app.config['UPLOAD_FOLDER'])

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


# returns content of given file, replaces includes by content of the included file
def get_file_content(fdir, fname):
    c = ''
    if os.path.isfile(os.path.join(fdir, fname)):
        with open(os.path.join(fdir, fname), "r") as f:
            c = f.readlines()

    content = ''
    for l in c:
        if '#include' in l:
            includefile = re.sub('#include ([\w,\s-]+\.[A-Za-z])', '\g<1>', l).strip()
            if os.path.isfile(os.path.join(fdir, includefile)):
                content += get_file_content(fdir, includefile)
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
    usermlnfiles, userdbs = get_example_files(mlnsession.tmpsessionfolder)

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


def get_cond_prob_png(queries, db, filename='cond_prob', filedir='/tmp'):
    declarations = r'''
    \DeclareMathOperator*{\argmin}{\arg\!\min}
    \DeclareMathOperator*{\argmax}{\arg\!\max}
    \newcommand{\Pcond}[1]{\ensuremath{P\left(\begin{array}{c|c}#1\end{array}\right)}}
    '''

    evidencelist = []
    out(db.evidence.keys())
    evidencelist.extend([e if db.evidence[e] == 1.0 else '!'+e for e in db.evidence.keys() ])
    query    = r'''\\'''.join([r'''\text{{ {0} }} '''.format(q.replace('_', '\_')) for q in queries])
    evidence = r'''\\'''.join([r'''\text{{ {0} }} '''.format(e.replace('_', '\_')) for e in evidencelist])
    eq       = r'''\argmax \Pcond{{ \begin{{array}}{{c}}{0}\end{{array}} & \begin{{array}}{{c}}{1}\end{{array}} }}'''.format(query, evidence)

    return math2png(eq, filedir, declarations=[declarations], filename=filename, size=10)
