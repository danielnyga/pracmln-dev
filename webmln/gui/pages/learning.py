import os
import logging
import traceback
from StringIO import StringIO
from flask import json, request, session, jsonify
from pracmln.praclog import logger
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import ensure_mln_session, change_example, get_training_db_paths
from pracmln import MLN, Database
from pracmln.mln.learning import DiscriminativeLearner
from pracmln.mln.methods import LearningMethods
from pracmln.mln.util import headline, out
from pracmln.utils.config import PRACMLNConfig, learn_config_pattern
from tabulate import tabulate

log = logger(__name__)


@mlnApp.app.route('/mln/learning/_start_learning', methods=['POST'])
def start_learning(savegeometry=True):
    mlnsession = ensure_mln_session(session)

    # initialize logger
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    sformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(sformatter)
    streamlog = logging.getLogger('streamlog')
    streamlog.setLevel(logging.INFO)
    streamlog.addHandler(handler)
    streamlog.info('start_learning')

    # load settings from webform
    data = json.loads(request.get_data())

    # update settings
    learnconfig = PRACMLNConfig(os.path.join(mlnsession.xmplFolder, learn_config_pattern % data['mln'].encode('utf8')))
    learnconfig.update(mlnsession.learnconfig.config)
    learnconfig.update(
        dict(mln_rename=data['mln_rename_on_edit'],
             db=data['db'].encode('utf8'), db_rename=data['db_rename_on_edit'],
             method=data['method'].encode('utf8'),
             params=data['params'].encode('utf8'),
             mln=data['mln'].encode('utf8'),
             output_filename=data['output'].encode('utf8'),
             logic=data['logic'].encode('utf8'),
             grammar=data['grammar'].encode('utf8'),
             multicore=data['multicore'], save=data['save_results'],
             ignore_unknown_preds=data['ignore_unknown_preds'],
             verbose=data['verbose'], use_prior=data['use_prior'],
             prior_mean=data['prior_mean'],
             prior_stdev=data['prior_stdev'],
             use_initial_weights=data['init_weights'],
             shuffle=data['shuffle'],
             qpreds=data['qpreds'].encode('utf8'),
             epreds=data['epreds'].encode('utf8'),
             discr_preds=data['discr_preds'],
             ignore_zero_weight_formulas=data['ignore_zero_weight_formulas'],
             incremental=data['incremental'],
             pattern=data['pattern'].encode('utf8')))

    if learnconfig['mln'] == "":
        raise Exception("No MLN was selected")

    out(learnconfig.config)

    # store settings in session
    mlnsession.learnconfig = learnconfig

    # expand the parameters
    tmpconfig = learnconfig.config.copy()
    if 'params' in tmpconfig:
        params = eval("dict(%s)" % learnconfig['params'])
        del tmpconfig['params']
        tmpconfig.update(params)

    # load the training databases
    pattern = tmpconfig["pattern"].strip()
    if pattern:
        dbs = get_training_db_paths(pattern)
    else:
        db = tmpconfig["db"]
        if db is None or not db:
            raise Exception('no trainig data given!')
        if os.path.exists(os.path.join(mlnsession.xmplFolderLearning, db)):
            dbs = [os.path.join(mlnsession.xmplFolderLearning, db)]
        elif os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], db)):
            dbs = [os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], db)]

    mlnsession.learnconfig = learnconfig

    # invoke learner
    learnedmln = ''
    try:
        print headline('PRACMLN LEARNING TOOL')

        # get the method class
        method = LearningMethods.clazz(tmpconfig['method'])

        if tmpconfig['verbose']:
            conf = dict(tmpconfig)
            print tabulate(
                sorted(list(conf.viewitems()), key=lambda (key, value): str(key)), headers=('Parameter:', 'Value:'))

        params = dict([(k, tmpconfig[k]) for k in ('multicore', 'verbose', 'ignore_zero_weight_formulas')])

        # for discriminative learning
        if issubclass(method, DiscriminativeLearner):
            if not tmpconfig['discr_preds']:  # use query preds
                params['qpreds'] = tmpconfig['qpreds'].split(',')
            elif tmpconfig['discr_preds']:  # use evidence preds
                params['epreds'] = tmpconfig['epreds'].split(',')

        # gaussian prior settings
        if tmpconfig["use_prior"]:
            params['prior_mean'] = float(tmpconfig["prior_mean"])
            params['prior_stdev'] = float(tmpconfig["prior_stdev"])

        try:
            # load the MLN
            if os.path.exists(os.path.join(mlnsession.xmplFolderLearning, tmpconfig["mln"])):
                mlnfile = os.path.join(mlnsession.xmplFolderLearning, tmpconfig["mln"])
            elif os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], tmpconfig["mln"])):
                mlnfile = os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], tmpconfig["mln"])
            mln = MLN(mlnfile=mlnfile, logic=tmpconfig['logic'], grammar=tmpconfig['grammar'])

            # load the databases
            dbs = reduce(list.__add__, [Database.load(mln, dbfile, tmpconfig['ignore_unknown_preds']) for dbfile in dbs])
            if tmpconfig['verbose']: log.info('loaded {} database(s).'.format(len(dbs)))

            # run the learner
            mlnlearnt = mln.learn(dbs, method, **params)

            # save result for visualization or whatever
            learnedmlnstream = StringIO()
            mlnlearnt.write(learnedmlnstream)
            mlnlearnt.write()
            learnedmln = learnedmlnstream.getvalue()

            if tmpconfig['verbose']:
                print
                print headline('LEARNT MARKOV LOGIC NETWORK')
                print
                mlnlearnt.write()

                log.info('LEARNT MARKOV LOGIC NETWORK')
                mlnlearnt.write(stream)
            if tmpconfig['save']:
                log.info('saving learned mln to {}...'.format(
                    os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], tmpconfig['output_filename'])))
                with open(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], tmpconfig['output_filename']), 'w+') as outFile:
                    mlnlearnt.write(outFile)
        except SystemExit:
            log.error('Cancelled...')
        finally:
            log.info('FINISHED')
            handler.flush()
    except:
        traceback.print_exc()

    output = stream.getvalue()
    res = {'output': output, 'learnedmln': learnedmln}
    return jsonify(res)


@mlnApp.app.route('/mln/learning/_change_example', methods=['POST'])
def change_example_lrn():
    data = json.loads(request.get_data())
    return change_example("learning", data['folder'])
