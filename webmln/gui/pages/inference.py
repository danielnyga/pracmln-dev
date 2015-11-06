import json
import logging
import traceback
import subprocess
from StringIO import StringIO
from flask import request, session, jsonify
import sys
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from pracmln.mln.methods import InferenceMethods
from pracmln.mln.util import parse_queries, out
from pracmln.praclog import logger
from pracmln.utils import config
from pracmln.utils.project import PRACMLNConfig
from pracmln.utils.visualization import get_cond_prob_png
from utils import ensure_mln_session, GUI_SETTINGS, change_example
from webmln.gui.app import mlnApp
import pracmln


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
    output = config.query_output_filename(data['mln'].encode('utf8'), InferenceMethods.id(data['method'].encode('utf8')), data['db'].encode('utf8'))
    mln_name = data['mln'].encode('utf8')
    db_name = data['db'].encode('utf8')
    emln_name = data['emln'].encode('utf8')

    # update settings
    inferconfig = PRACMLNConfig()
    inferconfig.update(mlnsession.projectinf.queryconf.config)
    inferconfig.update(
        dict(mln_rename=data['mln_rename_on_edit'],
             db=db_name, db_rename=data['db_rename_on_edit'],
             method=data['method'].encode('utf8'),
             params=data['params'].encode('utf8'),
             queries=data['query'].encode('utf8'),
             mln=mln_name, emln=emln_name,
             output_filename=output,
             cw=data['closed_world'], cw_preds=map(str.strip, str(data['cw_preds']).split(',')),
             use_emln=data['use_emln'], logic=data['logic'].encode('utf8'),
             grammar=data['grammar'].encode('utf8'),
             multicore=data['multicore'], save=True,
             ignore_unknown_preds=data['ignore_unknown_preds'],
             verbose=data['verbose']))

    # store settings in session
    mlnsession.projectinf.learnconf.conf = inferconfig.config.copy()

    barchartresults = []
    graphres = []
    png = ''
    ratio = 1
    try:
        # expand the parameters
        tmpconfig = inferconfig.config.copy()
        if 'params' in tmpconfig:
            params = eval("dict(%s)" % inferconfig.get('params', ''))
            del tmpconfig['params']
            tmpconfig.update(params)

        # create the MLN and evidence database and the parse the queries
        modelstr = mln_content + (emln_content if tmpconfig.get('use_emln', False) and emln_content != '' else '')
        mln = parse_mln(modelstr, searchpaths=[mlnsession.tmpsessionfolder], projectpath=mlnsession.tmpsessionfolder, logic=tmpconfig.get('logic', 'FirstOrderLogic'), grammar=tmpconfig.get('grammar', 'PRACGrammar'))
        db = parse_db(mln, db_content, ignore_unknown_preds=tmpconfig.get('ignore_unknown_preds', False))

        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        else:
            db = db[0]

        # parse non-atomic params
        queries = tmpconfig.get('queries', pracmln.ALL)
        if isinstance(queries, basestring):
            queries = parse_queries(mln, queries)
        tmpconfig['cw_preds'] = filter(lambda x: bool(x), tmpconfig['cw_preds'])

        # extract and remove all non-algorithm
        method = InferenceMethods.clazz(tmpconfig.get('method', 'MCSAT'))
        for s in GUI_SETTINGS:
            if s in tmpconfig: del tmpconfig[s]

        try:
            mln_ = mln.materialize(db)
            mrf = mln_.ground(db)

            if inferconfig.get('verbose', False):
                streamlog.info('EVIDENCE VARIABLES')
                mrf.print_evidence_vars(stream)

            inference = method(mrf, queries, **tmpconfig)
            result = inference.run()

            output = StringIO()
            result.write(output)
            res = output.getvalue()

            if inferconfig.get('verbose', False):
                streamlog.info('INFERENCE RESULTS: \n' + res)

            graphres = calculategraphres(mrf, db.evidence.keys(), inference.queries)
            barchartresults = [{"name": x, "value": inference.results[x]} for x in inference.results]

            png, ratio = get_cond_prob_png(queries, db, filedir=mlnsession.tmpsessionfolder)

            # save settings to project
            if inferconfig.get('save', False):
                log.info('trying to save results')
                fname = inferconfig.get('output_filename', 'inference.result')
                mlnsession.projectinf.add_result(fname, res)
                mlnsession.projectinf.mlns[mln_name] = mln_content
                mlnsession.projectinf.emlns[mln_name] = emln_content
                mlnsession.projectinf.dbs[db_name] = db_content
                mlnsession.projectinf.save(dirpath=mlnsession.tmpsessionfolder)
                streamlog.info('saved result to file results/{} in project {}'.format(fname, mlnsession.projectinf.name))

            streamlog.info('FINISHED')

        except SystemExit:
            streamlog.error('Cancelled...')
        finally:
            handler.flush()
    except:
        traceback.print_exc(file=stream)
    finally:
        return jsonify({'graphres': graphres, 'resbar': barchartresults,
                    'output': stream.getvalue(),
                    'condprob': {'png': png, 'ratio': ratio}})


@mlnApp.app.route('/mln/inference/_use_model_ext', methods=['GET', 'OPTIONS'])
def get_emln():
    mln_session = mlnApp.session_store[session]
    emlnfiles = mln_session.projectinf.emlns.keys()
    emlnfiles.sort()

    return jsonify({"emlnfiles": emlnfiles})


# calculates links from the mrf groundformulas
# for each ground formula, a fully connected
# subgraph is calculated. Bidirectional relations are
# ignored to avoid duplicate links
# 'type' will be used to determine
# the circle color during graph drawing
def calculategraphres(resmrf, evidence, queries):
    permutations = []
    linkformulas = []
    for formula in resmrf.itergroundings():
        gatoms = sorted(formula.gndatoms(), key=lambda entry: str(entry))
        perms = perm(gatoms)
        permutations.extend(perms)
        linkformulas.extend([str(formula)]*len(perms))
    links = []

    for i, p in enumerate(permutations):
        sourceev = "evidence" if str(p[0]) in evidence else "query" if p[0] in queries else "hiddenCircle"
        targetev = "evidence" if str(p[1]) in evidence else "query" if p[1] in queries else "hiddenCircle"

        lnk = {'source': {'name': str(p[0]), 'type': sourceev},
               'target': {'name': str(p[1]), 'type': targetev},
               'value': linkformulas[i],
               'arcStyle': 'strokegreen'}

        links.append(lnk) #may contain duplicate links
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
