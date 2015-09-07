import os
import json
import logging
import traceback
import subprocess
from StringIO import StringIO
from fnmatch import fnmatch
from flask import request, session, jsonify
import sys
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from pracmln.mln.methods import InferenceMethods
from pracmln.mln.util import parse_queries, out
from pracmln.praclog import logger
from pracmln.utils.config import query_config_pattern, PRACMLNConfig
from utils import ensure_mln_session, GUI_SETTINGS, change_example, \
    get_cond_prob_png
from webmln.gui.app import mlnApp

log = logger(__name__)

DEBUG = False
SECRET_KEY = 'secret'
USERNAME = 'admin'
PASSWORD = 'default'


def call(args):
    try:
        subprocess.call(args)
    except OSError:
        args = list(args)
        args[0] += ".bat"
        subprocess.call(args)


@mlnApp.app.route('/mln/inference/_change_example', methods=['POST'])
def change_example_inf():
    data = json.loads(request.get_data())
    return change_example("inference", data['folder'])


@mlnApp.app.route('/mln/inference/_start_inference', methods=['POST'])
def start_inference():
    mlnsession = ensure_mln_session(session)
    
    # initialize logger
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    sformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(sformatter)
    streamlog = logging.getLogger('streamlog')
    streamlog.setLevel(logging.INFO)
    streamlog.addHandler(handler)
    streamlog.info('STARTING INFERENCE')
    sys.stdout = stream


    # load settings from webform
    data = json.loads(request.get_data())
    mln_content = data['mln_text'].encode('utf8')
    db_content = data['db_text'].encode('utf8')
    emln_content = data['emln_text'].encode('utf8')

    # update settings
    inferconfig = PRACMLNConfig(os.path.join(mlnsession.xmplFolder, query_config_pattern % data['mln'].encode('utf8')))
    inferconfig.update(mlnsession.inferconfig.config)
    inferconfig.update(
        dict(mln_rename=data['mln_rename_on_edit'],
             db=data['db'].encode('utf8'), db_rename=data['db_rename_on_edit'],
             method=data['method'].encode('utf8'),
             params=data['params'].encode('utf8'),
             queries=data['query'].encode('utf8'),
             mln=data['mln'].encode('utf8'), emln=data['emln'].encode('utf8'),
             output_filename="",
             cw=data['closed_world'], cw_preds=data['cw_preds'],
             use_emln=data['use_emln'], logic=data['logic'].encode('utf8'),
             grammar=data['grammar'].encode('utf8'),
             multicore=data['use_multicpu'], save=False,
             ignore_unknown_preds=data['ignore_unknown_preds'],
             verbose=data['verbose']))

    # store settings in session
    mlnsession.inferconfig = inferconfig

    barchartresults = []
    graphres = []
    png = ''
    ratio = 1
    try:
        # expand the parameters
        tmpconfig = inferconfig.config.copy()
        if 'params' in tmpconfig:
            params = eval("dict(%s)" % inferconfig['params'])
            del tmpconfig['params']
            tmpconfig.update(params)

        # create the MLN and evidence database and the parse the queries
        modelstr = mln_content + (emln_content if tmpconfig['use_emln'] not in (None, '') and emln_content != '' else '')
        mln = parse_mln(modelstr, searchPath=mlnsession.xmplFolder, logic=tmpconfig['logic'], grammar=tmpconfig['grammar'])
        db = parse_db(mln, db_content, ignore_unknown_preds=tmpconfig.get('ignore_unknown_preds', False))

        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        else:
            db = db[0]

        # parse non-atomic params
        queries = parse_queries(mln, str(tmpconfig['queries']))
        cw_preds = filter(lambda x: x != "", map(str.strip, str(
            tmpconfig["cw_preds"].split(",")))) if 'cw_preds' in tmpconfig else []
        if tmpconfig['cw']:
            cw_preds = [p.name for p in mln.predicates if p.name not in queries]

        # extract and remove all non-algorithm
        method = tmpconfig.get('method', 'MCSAT')
        for s in GUI_SETTINGS:
            if s in tmpconfig: del tmpconfig[s]

        try:
            mln_ = mln.materialize(db)
            mrf = mln_.ground(db, cwpreds=cw_preds)
            if inferconfig.get('verbose', False):
                streamlog.info('EVIDENCE VARIABLES')
                mrf.print_evidence_vars(stream)
            inference = InferenceMethods.clazz(method)(mrf, queries, **tmpconfig)
            inference.run()

            if inferconfig.get('verbose', False):
                streamlog.info('INFERENCE RESULTS')
                inference.write(stream, color=None)

            graphres = calculategraphres(mrf, db.evidence.keys(), inference.queries)
            barchartresults =  [{"name":x, "value":inference.results[x]} for x in inference.results]

            png, ratio = get_cond_prob_png(queries, db)

        except SystemExit:
            streamlog.error('Cancelled...')
        finally:
            streamlog.info('FINISHED')
            handler.flush()
    except:
        traceback.print_exc()

    return jsonify({'graphres': graphres, 'resbar': barchartresults,
                    'output': stream.getvalue(),
                    'condprob': {'png': png, 'ratio': ratio}})


@mlnApp.app.route('/mln/inference/_use_model_ext', methods=['GET', 'OPTIONS'])
def get_emln():
    log.info('_use_model_ext')
    emlns = []
    for filename in os.listdir('.'):
        if fnmatch(filename, '*.emln'):
            emlns.append(filename)
    emlns.sort()
    if len(emlns) == 0:
        emlns.append("(no %s files found)" % str('*.emln'))
    return ','.join(emlns)


# calculates links from the mrf groundformulas
# for each ground formula, a fully connected
# subgraph is calculated. Bidirectional relations are
# ignored to avoid duplicate links
# 'type' will be used to determine
# the circle color during graph drawing
def calculategraphres(resmrf, evidence, queries):
    permutations = []
    for formula in resmrf.itergroundings():
        gatoms = sorted(formula.gndatoms(), key=lambda entry: str(entry))
        permutations.extend(perm(gatoms))
    links = []
    for p in permutations:
        sourceev = "evidence" if str(p[0]) in evidence else "query" if p[0] in queries else "hidden"
        targetev = "evidence" if str(p[1]) in evidence else "query" if p[1] in queries else "hidden"

        lnk = {'source': {'name': str(p[0]), 'type': sourceev},
               'target': {'name': str(p[1]), 'type': targetev},
               'value': str(formula),
               'arcStyle': 'strokegreen'}
        if lnk in links: continue
        links.append(lnk)
    return links


# returns useful combinations of the list items.
# ignores atoms with two identical arguments (e.g. Friends(Bob, Bob))
# and duplicates
def perm(list):
    res = []
    for i, val in enumerate(list):
        for y, val2 in enumerate(list):
            if i >= y: continue
            if (val, val2) in res: continue
            res.append((val, val2))
    return res
