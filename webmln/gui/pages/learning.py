from StringIO import StringIO
import logging
import os
import traceback
from flask import json, request, session, jsonify
import sys
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import ensure_mln_session, dump, \
    change_example, get_training_db_paths
from pracmln import MLN, Database
from pracmln.mln.learning import DiscriminativeLearner
from pracmln.mln.methods import LearningMethods
from pracmln.mln.util import headline
from pracmln.utils.config import PRACMLNConfig, learn_config_pattern
from tabulate import tabulate

@mlnApp.app.route('/mln/learning/_start_learning', methods=['POST'])
def start_learning(saveGeometry=True):

    # initialize logger
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    # sformatter = logging.Formatter("%(message)s\n")
    sformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(sformatter)
    log = logging.getLogger('streamlog')
    log.setLevel(logging.INFO)
    log.addHandler(handler)

    # update settings;
    log.info('start_learning')
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())

    mln = data['mln'].encode('utf8')
    db = data['db'].encode('utf8')
    mln_content = data['mln_text'].encode('utf8')
    db_content = data['db_text'].encode('utf8')
    output = data['output'].encode('utf8')
    method = data['method'].encode('utf8')
    params = data['params'].encode('utf8')


    # update settings
    settings = mlnsession.settingsL
    if mln == "":
        raise Exception("No MLN was selected")
    params = params
    verbose = data['verbose']
    if not os.path.exists(mlnApp.app.config['UPLOAD_FOLDER']):
        os.mkdir(mlnApp.app.config['UPLOAD_FOLDER'])
    settings = PRACMLNConfig(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], learn_config_pattern % mln))
    settings["mln"] = mln
    settings["db"] = db
    settings["output_filename"] = output
    settings["params"] = params
    settings["method"] = LearningMethods.id(method)
    settings["pattern"] = data['pattern'].encode('utf8')
    settings["use_prior"] = data['use_prior']
    settings["prior_mean"] = data['prior_mean']
    settings["prior_stdev"] = data['prior_stdev']
    settings["incremental"] = data['incremental']
    settings["shuffle"] = data['shuffle']
    settings["use_initial_weights"] = data['init_weights']
    settings["qpreds"] = data['qpreds'].encode('utf8')
    settings["epreds"] = data['epreds'].encode('utf8')
    settings["discr_preds"] = data['discr_preds']
    settings['logic'] = data['logic'].encode('utf8')
    settings['grammar'] = data['grammar'].encode('utf8')
    settings['multicore'] = data['multicore']
    settings['verbose'] = verbose
    settings['ignore_unknown_preds'] = data['ignore_unknown_preds']
    settings['ignore_zero_weight_formulas'] = data['ignore_zero_weight_formulas']
    settings['save'] = data['save']

    # write settings
    log.info('writing config...')
    settings.dump()

    # load the training databases
    pattern = settings["pattern"].strip()
    if pattern:
        dbs = get_training_db_paths()
    else:
        if db is None or not db:
            raise Exception('no trainig data given!')
        if os.path.exists(os.path.join(mlnsession.xmplFolderLearning, db)):
            dbs = [os.path.join(mlnsession.xmplFolderLearning, db)]
        elif os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], db)):
            dbs = [os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], db)]


    mlnsession.settingsL = settings

    # invoke learner
    try:
        print headline('PRACMLN LEARNING TOOL')

        # get the method class
        method = LearningMethods.clazz(settings['method'])

        if verbose:
            conf = dict(settings.config)
            conf.update(settings['params'])
            print tabulate(sorted(list(conf.viewitems()), key=lambda (k,v): str(k)), headers=('Parameter:', 'Value:'))

        params = {}
        params = dict([(k, settings[k]) for k in ('multicore', 'verbose', 'ignore_zero_weight_formulas')])

        # for discriminative learning
        if issubclass(method, DiscriminativeLearner):
            if settings['discr_preds'] == False: # use query preds
                params['qpreds'] = settings['qpreds'].split(',')
            elif settings['discr_preds'] == True: # use evidence preds
                params['epreds'] = settings['epreds'].split(',')

        # gaussian prior settings
        if settings["use_prior"]:
            params['prior_mean'] = float(settings["prior_mean"])
            params['prior_stdev'] = float(settings["prior_stdev"])
        # expand the parameters
        params.update(eval("dict(%s)" % settings['params']))

        learnedmln = ''
        try:
            # load the MLN
            if os.path.exists(os.path.join(mlnsession.xmplFolderLearning, settings["mln"])):
                mlnfile = os.path.join(mlnsession.xmplFolderLearning, settings["mln"])
            elif os.path.exists(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], settings["mln"])):
                mlnfile = os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], settings["mln"])
            mln = MLN(mlnfile=mlnfile, logic=settings['logic'], grammar=settings['grammar'])
            # load the databases

            dbs = reduce(list.__add__, [Database.load(mln, dbfile, settings['ignore_unknown_preds']) for dbfile in dbs])
            if verbose: log.info('loaded {} database(s).'.format(len(dbs)))

            # run the learner
            mlnlearnt = mln.learn(dbs, method, **params)

            # save result for visualization or whatever
            learnedmlnStream = StringIO()
            mlnlearnt.write(learnedmlnStream)
            learnedmln = learnedmlnStream.getvalue()

            if verbose:
                print
                print headline('LEARNT MARKOV LOGIC NETWORK')
                print
                mlnlearnt.write()

                log.info('LEARNT MARKOV LOGIC NETWORK')
                mlnlearnt.write(stream)
            if settings['save']:
                log.info('saving learned mln to {}...'.format(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], output)))
                with open(os.path.join(mlnApp.app.config['UPLOAD_FOLDER'], output), 'w+') as outFile:
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
    return jsonify( res )


@mlnApp.app.route('/mln/learning/_change_example', methods=['POST'])
def change_example_lrn():
    data = json.loads(request.get_data())
    return change_example("learning", data['folder'])
