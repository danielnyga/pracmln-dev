from StringIO import StringIO
import json
import os
import sys
import pickle
from fnmatch import fnmatch
from multiprocessing.queues import Queue
import subprocess

from flask import request, session, jsonify, send_from_directory

from webmln.mlninit import mlnApp
from pracmln.mln.inference import *
from pracmln.mln.methods import InferenceMethods
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from pracmln.mln.util import parse_queries

import logging
import traceback
from utils import ensure_mln_session, getFileContent, QUERY_CONFIG_PATTERN, \
    GUI_SETTINGS

DEBUG = False
SECRET_KEY = 'secret'
USERNAME = 'admin'
PASSWORD = 'default'

INFERENCE_METHODS = InferenceMethods.getNames()
DEFAULT_EXAMPLE = 'smokers'

# separate logger for user statistics
stream = StringIO()
handler = logging.StreamHandler(stream)
# sformatter = logging.Formatter("%(message)s\n")
sformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(sformatter)
log = logging.getLogger('streamlog')
log.setLevel(logging.INFO)
log.addHandler(handler)

def call(args):
    try:
        subprocess.call(args)
    except:
        args = list(args)
        args[0] = args[0] + ".bat"
        subprocess.call(args)

@mlnApp.app.route('/mln/static/<path:filename>')
def download_static(filename):
    return send_from_directory(mlnApp.app.config['MLN_STATIC_PATH'], filename)


@mlnApp.app.route('/mln/_get_filecontent', methods=['POST'])
def load_filecontent():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    filename = data['filename']
    xmplFolder = data['example']
    text = ''

    if os.path.exists(os.path.join(mlnsession.xmplFolder, filename)):
        text = getFileContent(mlnsession.xmplFolder, filename)
    elif os.path.exists(os.path.join('/tmp', 'tempupload', filename)):
        text = getFileContent(os.path.join('/tmp', 'tempupload'), filename)

    return jsonify( {'text': text} )

@mlnApp.app.route('/mln/_change_example', methods=['POST'])
def change_example():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    mlnsession.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], data['folder'])
    mlnFiles, dbs = getExampleFiles(mlnsession.xmplFolder)
    userMLNFiles, userDBS = getExampleFiles(os.path.join('/tmp', 'tempupload'))

    return jsonify( {'dbs': dbs + userDBS, 'mlns': mlnFiles + userMLNFiles} )


class StdoutQueue(Queue):
    def __init__(self,*args,**kwargs):
        Queue.__init__(self,*args,**kwargs)

    def write(self,msg):
        self.put(msg)

    def flush(self):
        sys.__stdout__.flush()

@mlnApp.app.route('/mln/_start_inference', methods=['POST'])
def start_inference():

    log.info('start_inference')
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())

    mln = data['mln'].encode('utf8')
    emln = data['emln'].encode('utf8')
    db = data['db'].encode('utf8')
    mln_content = data['mln_text'].encode('utf8')
    db_content = data['db_text'].encode('utf8')
    emln_content = data['emln_text'].encode('utf8')
    output = data['output'].encode('utf8')
    method = data['method'].encode('utf8')
    params = data['params'].encode('utf8')


    # update settings
    settings = mlnsession.settings

    settings["mln_rename"] = data['mln_rename_on_edit']
    settings["db"] = db
    settings["db_rename"] = data['db_rename_on_edit']
    settings["method"] = method
    settings["params"] = params
    settings["queries"] = data['query'].encode('utf8')
    settings['emln'] = emln
    settings["output_filename"] = output
    settings["cw"] = data['closed_world']
    settings["cw_preds"] = data['cw_preds']
    settings["use_emln"] = data['use_emln']
    settings['logic'] = data['logic'].encode('utf8')
    settings['grammar'] = data['grammar'].encode('utf8')
    settings['multicore'] = data['use_multicpu']
    settings['save'] = data['save_results']
    settings['ignore_unknown_preds'] = data['ignore_unknown_preds']
    settings['verbose'] = data['verbose'].encode('utf8')


    # store settings in session
    mlnsession.settings = settings

    atoms = []
    formulas = []
    resultKeys = []
    resultValues = []
    try:
        # expand the parameters
        params = settings.copy()
        if 'params' in params:
            params.update(eval("dict(%s)" % params['params']))
            del params['params']
        # create the MLN and evidence database and the parse the queries
        modelstr = mln_content + (emln_content if params['use_emln'] not in (None, '') and emln_content != '' else '')
        mln = parse_mln(modelstr, searchPath=mlnsession.xmplFolder, logic=params['logic'], grammar=params['grammar'])
        db = parse_db(mln, db_content, ignore_unknown_preds=params.get('ignore_unknown_preds', False))
        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        else:
            db = db[0]
        # parse non-atomic params
        queries = parse_queries(mln, str(params['queries']))
        cw_preds = filter(lambda x: x != "", map(str.strip, str(params["cw_preds"].split(",")))) if 'cw_preds' in params else []
        if params['cw']:
            cw_preds = [p.name for p in mln.predicates if p.name not in queries]

        # extract and remove all non-algorithm
        method = params.get('method', 'MC-SAT')
        for s in GUI_SETTINGS:
            if s in params: del params[s]

        try:
            mln_ = mln.materialize(db)
            mrf = mln_.ground(db, cwpreds=cw_preds)
            if params.get('verbose', False):
                log.info('EVIDENCE VARIABLES')
                mrf.print_evidence_vars()
            inference = eval(InferenceMethods.byName(method))(mrf, queries, **params)
            inference.run()

            # generate output for graph and bar chart
            atoms =  mrf._gndatoms.keys()
            formulas = []
            for i in mrf.itergroundings():
                formulas.append(str(i))
            results = {}
            for gndf, p in mrf.evidence_dicts().iteritems():
                results[str(gndf)] = p

            resultKeys = results.keys()
            resultValues = results.values()

            log.info('INFERENCE RESULTS')
            inference.write(stream)
            if settings['save']:
                with open(os.path.join(mlnsession.xmplFolder, output), 'w+') as outFile:
                    inference.write(outFile)
        except SystemExit:
            log.error('Cancelled...')
        finally:
            log.info('FINISHED')
            handler.flush()
    except:
        traceback.print_exc()

    output = stream.getvalue()
    res = {'atoms': atoms, 'formulas': formulas, 'resultkeys': resultKeys, 'resultvalues': resultValues, 'output': output}
    return jsonify( res )


@mlnApp.app.route('/mln/_use_model_ext', methods=['GET', 'OPTIONS'])
def get_emln():
    log.info('_use_model_ext')
    emlns = []
    for filename in os.listdir('.'):
        if fnmatch(filename, '*.emln'):
            emlns.append(filename)
    emlns.sort()
    if len(emlns) == 0: emlns.append("(no %s files found)" % str('*.emln'))
    return ','.join(emlns)

@mlnApp.app.route('/mln/_init', methods=['GET', 'OPTIONS'])
def init_options():
    log.info('_init/ init_options')
    mlnsession = ensure_mln_session(session)
    mlnFiles, dbFiles = getExampleFiles(mlnsession.xmplFolder)
    dirs = [x for x in os.listdir(mlnApp.app.config['EXAMPLES_FOLDER']) if os.path.isdir(os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'],x))]
    res = { 'infMethods': INFERENCE_METHODS,
            'files':mlnFiles,
            'dbs': dbFiles,
            'queries': mlnsession.settings['queries'],
            'maxSteps': mlnsession.settings['maxSteps'],
            'examples': dirs}
    return jsonify( res )


def initialize():
    log.info('initialize')
    mlnsession = ensure_mln_session(session)
    mlnsession.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
    mlnsession.params = ''

    confignames = ["mlnquery.config.dat", "query.config.dat"]
    settings = {}
    for filename in confignames:
        configname = os.path.join(mlnsession.xmplFolder, filename)
        print configname, os.path.exists(configname)
        if os.path.exists(configname):
            try:
                settings = pickle.loads("\n".join(map(lambda x: x.strip(
                    "\r\n"), file(configname, "r").readlines())))
            except:
                log.info('Could not load file {}'.format(configname))
            break

    mlnsession.settings = settings

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
