import ctypes
import time
import json
import logging
from threading import Thread
import traceback
import subprocess
from StringIO import StringIO
from flask import request, session, jsonify
import sys
import multiprocessing as mp
import io
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from pracmln.mln.methods import InferenceMethods
from pracmln.mln.util import parse_queries
from pracmln.praclog import logger
from pracmln.utils import config
from pracmln.utils.project import PRACMLNConfig
from pracmln.utils.visualization import get_cond_prob_png
from utils import ensure_mln_session, GUI_SETTINGS, change_example
from webmln.gui.app import mlnApp
import pracmln
from webmln.gui.pages.buffer import RequestBuffer


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
    data = json.loads(request.get_data())

    if data.get('timeout') is None:
        timeout = None
    elif data.get('timeout').encode('utf8') != '':
        timeout = float(data.get('timeout').encode('utf8'))
    else:
        timeout = 120

    log.info('starting inference with timeout of {}'.format(timeout))
    mlnsession.infbuffer = RequestBuffer()
    t = Thread(target=infer, args=(mlnsession, data, timeout))
    t.start()
    mlnsession.infbuffer.waitformsg()
    return jsonify(mlnsession.infbuffer.content)


@mlnApp.app.route('/mln/inference/_get_status', methods=['POST'])
def getinfstatus():
    mlnsession = ensure_mln_session(session)
    mlnsession.infbuffer.waitformsg()
    return jsonify(mlnsession.infbuffer.content)


def infer(mlnsession, data, to):

    mlnsession.log.info('STARTING INFERENCE')
    sys.stdout = mlnsession.stream

    # load settings from webform
    mln_content = data['mln_text'].encode('utf8')
    db_content = data['db_text'].encode('utf8')
    emln_content = data['emln_text'].encode('utf8')
    output = config.query_output_filename(data['mln'].encode('utf8'),
                                          InferenceMethods.id(data['method']
                                                              .encode('utf8')),
                                          data['db'].encode('utf8'))
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
             cw=data['closed_world'],
             cw_preds=map(str.strip, str(data['cw_preds']).split(',')),
             use_emln=data['use_emln'], logic=data['logic'].encode('utf8'),
             grammar=data['grammar'].encode('utf8'),
             multicore=data['multicore'], save=True,
             ignore_unknown_preds=data['ignore_unknown_preds'],
             verbose=data['verbose']))

    # store settings in session
    mlnsession.projectinf.learnconf.conf = inferconfig.config.copy()
    mlnsession.infbuffer.setmsg({'message': 'Creating MLN and DB objects may'
                                            ' take a while...',
                                 'status': False})
    time.sleep(1)
    barchartresults = []
    graphres = []
    png = ''
    ratio = 1
    message = ''
    res = ''
    try:
        # expand the parameters
        tmpconfig = inferconfig.config.copy()
        if 'params' in tmpconfig:
            params = eval("dict(%s)" % inferconfig.get('params', ''))
            del tmpconfig['params']
            tmpconfig.update(params)

        # create the MLN and evidence database and the parse the queries
        modelstr = mln_content + \
                   (emln_content if tmpconfig.get('use_emln',
                                                  False) and emln_content != '' else '')

        mln = parse_mln(modelstr,
                        searchpaths=[mlnsession.tmpsessionfolder],
                        projectpath=mlnsession.tmpsessionfolder,
                        logic=tmpconfig.get('logic', 'FirstOrderLogic'),
                        grammar=tmpconfig.get('grammar', 'PRACGrammar'))
        db = parse_db(mln, db_content,
                      ignore_unknown_preds=tmpconfig.get(
                          'ignore_unknown_preds',
                          False))

        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        else:
            db = db[0]

        # parse non-atomic params
        queries = tmpconfig.get('queries', pracmln.ALL)
        if isinstance(queries, basestring):
            queries = parse_queries(mln, queries)
        tmpconfig['cw_preds'] = filter(lambda b: bool(b),
                                       tmpconfig['cw_preds'])

        # extract and remove all non-algorithm
        method = InferenceMethods.clazz(tmpconfig.get('method', 'MCSAT'))
        for s in GUI_SETTINGS:
            if s in tmpconfig:
                del tmpconfig[s]

        try:
            mln_ = mln.materialize(db)
            mrf = mln_.ground(db)

            if inferconfig.get('verbose', False):
                mlnsession.log.info('EVIDENCE VARIABLES')
                mrf.print_evidence_vars(mlnsession.stream)

            inference = method(mrf, queries, **tmpconfig)
            mlnsession.infbuffer.setmsg({'message': 'Starting Inference...',
                                         'status': False})

            # VarI - inference will be cancelled on timeout
            # if multicore enabled, there may still be processes running
            # in the background
            # success, result = RunProcess(inference.run, timeout).Run()
            # if success:
            #     res = result.get('res')
            #     result = result.get('result')
            # else:
            #     raise mp.TimeoutError
            # if inferconfig.get('verbose', False):
            #     streamlog.info('INFERENCE RESULTS: \n' + res)

            # VarII - inference cannot be cancelled
            # inference.run()
            # results = inference.results

            # VarIII - inference will be cancelled on timeout
            # if multicore enabled, there may still be processes running
            # in the background
            t = Thread(target=inference.run, args=())
            t.start()
            threadid = t.ident
            t.join(to)  # wait until either thread is done or time is up

            if t.isAlive():
                # stop inference and raise TimeoutError locally
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_long(threadid),
                    ctypes.py_object(SystemExit))
                raise mp.TimeoutError

            results = inference.results

            if inferconfig.get('verbose', False):
                output = io.BytesIO()
                inference.write(output)
                res = output.getvalue()
                mlnsession.log.info('INFERENCE RESULTS: \n' + res)

            graphres = calculategraphres(mrf,
                                         db.evidence.keys(),
                                         inference.queries)
            barchartresults = [{"name": x,
                                "value": results[x]} for x in results]

            png, ratio = get_cond_prob_png(queries,
                                           db,
                                           filedir=mlnsession.tmpsessionfolder)

            # save settings to project
            if inferconfig.get('save', False):
                fname = inferconfig.get('output_filename', 'inference.result')
                mlnsession.projectinf.add_result(fname, res)
                mlnsession.projectinf.mlns[mln_name] = mln_content
                mlnsession.projectinf.emlns[mln_name] = emln_content
                mlnsession.projectinf.dbs[db_name] = db_content
                mlnsession.projectinf.save(dirpath=mlnsession.tmpsessionfolder)
                mlnsession.log.info('saved result to file results/{} in project {}'
                               .format(fname, mlnsession.projectinf.name))

            mlnsession.log.info('FINISHED')

        except SystemExit:
            mlnsession.log.error('Cancelled...')
            message = 'Cancelled!\nCheck log for more information.'
        except mp.TimeoutError:
            mlnsession.log.error('Timeouterror! '
                            'Inference took more than {} seconds. '
                            'Increase the timeout and try again.'.format(to))
            message = 'Timeout!'
        finally:
            mlnsession.loghandler.flush()
    except:
        traceback.print_exc(file=mlnsession.stream)
        message = 'Failed!\nCheck log for more information.'
    finally:
        mlnsession.infbuffer.setmsg({'message': message,
                                     'status': True,
                                     'graphres': graphres,
                                     'resbar': barchartresults,
                                     'output': mlnsession.stream.getvalue(),
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
        linkformulas.extend([str(formula)] * len(perms))
    links = []

    for i, p in enumerate(permutations):
        sourceev = "evidence" if str(p[0]) in evidence else "query" \
            if p[0] in queries else "hiddenCircle"
        targetev = "evidence" if str(p[1]) in evidence else "query" \
            if p[1] in queries else "hiddenCircle"

        lnk = {'source': {'name': str(p[0]), 'type': sourceev},
               'target': {'name': str(p[1]), 'type': targetev},
               'value': linkformulas[i],
               'arcStyle': 'strokegreen'}

        links.append(lnk)  # may contain duplicate links
    return links


# returns useful combinations of the list items.
# ignores atoms with two identical arguments (e.g. Friends(Bob, Bob))
# and duplicates
def perm(l):
    res = []
    for i, val in enumerate(l):
        for y, val2 in enumerate(l):
            if i >= y:
                continue
            if (val, val2) in res:
                continue
            res.append((val, val2))
    return res
