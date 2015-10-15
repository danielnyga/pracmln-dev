import os
import logging
import traceback
from StringIO import StringIO
from flask import json, request, session, jsonify
import sys
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from pracmln.praclog import logger
from pracmln.utils import config
from webmln.gui.app import mlnApp
from webmln.gui.pages.utils import ensure_mln_session, change_example, get_training_db_paths
from pracmln import Database, MLNLearn
from pracmln.mln.methods import LearningMethods
from pracmln.utils.config import PRACMLNConfig

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
    streamlog.info('STARTING LEARNING')
    sys.stdout = stream

    # load settings from webform
    data = json.loads(request.get_data())
    mln_content = data['mln_text'].encode('utf8')
    db_content = data['db_text'].encode('utf8')
    output = config.learnwts_output_filename(data['mln'].encode('utf8'), LearningMethods.id(data['method'].encode('utf8')), data['db'].encode('utf8'))
    mln_name = data['mln'].encode('utf8')
    db_name = data['db'].encode('utf8')

    # update settings
    learnconfig = PRACMLNConfig()
    learnconfig.update(mlnsession.projectlearn.learnconf.config)
    learnconfig.update(
        dict(mln_rename=data['mln_rename_on_edit'],
             db=db_name, db_rename=data['db_rename_on_edit'],
             method=data['method'].encode('utf8'),
             params=data['params'].encode('utf8'),
             mln=mln_name,
             output_filename=output,
             logic=data['logic'].encode('utf8'),
             grammar=data['grammar'].encode('utf8'),
             multicore=data['multicore'], save=True,
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

    if learnconfig.get('mln', None) is None or learnconfig.get('mln', None) == "":
        raise Exception("No MLN was selected")

    # store settings in session
    mlnsession.projectlearn.learnconf.conf = learnconfig.config.copy()

    learnedmln = ''
    try:
        mlnobj = parse_mln(mln_content, searchpaths=[mlnsession.tmpsessionfolder], projectpath=os.path.join(mlnsession.tmpsessionfolder, mlnsession.projectlearn.name), logic=learnconfig.get('logic', 'FirstOrderLogic'), grammar=learnconfig.get('grammar', 'PRACGrammar'))

        if learnconfig.get('pattern'):
            local, dblist = get_training_db_paths(learnconfig.get('pattern', '').strip())
            dbobj = []
            # build database list from project dbs
            if local:
                for dbname in dblist:
                    dbobj.extend(parse_db(mlnobj, mlnsession.projectlearn.dbs[dbname].strip(), ignore_unknown_preds=learnconfig.get('ignore_unknown_preds', True)))
            # build database list from filesystem dbs
            else:
                for dbpath in dblist:
                    dbobj.extend(Database.load(mlnobj, dbpath, ignore_unknown_preds=learnconfig.get('ignore_unknown_preds', True)))
        # build single db from currently selected db
        else:
            dbobj = parse_db(mlnobj, db_content, ignore_unknown_preds=learnconfig.get('ignore_unknown_preds', True))


        # run the learner
        learning = MLNLearn(config=learnconfig, mln=mlnobj, db=dbobj)
        result = learning.run()

        output = StringIO()
        result.write(output, color=None)
        learnedmln = output.getvalue()

        if learnconfig.get('verbose', False):
            streamlog.info('LEARNT MARKOV LOGIC NETWORK: \n' + learnedmln)

        # save settings to project
        if learnconfig.get('save', False):
            fname = learnconfig.get('output_filename', 'result.mln')
            mlnsession.projectlearn.add_mln(fname, learnedmln)
            mlnsession.projectlearn.mlns[mln_name] = mln_content
            mlnsession.projectlearn.dbs[db_name] = db_content
            mlnsession.projectlearn.save(dirpath=mlnsession.tmpsessionfolder)
            streamlog.info('saved result to file results/{} in project {}'.format(fname, mlnsession.projectlearn.name))

    except SystemExit:
        log.error('Cancelled...')
    except:
        traceback.print_exc()
    finally:
        log.info('FINISHED')
        handler.flush()

    output = stream.getvalue()
    res = {'output': output, 'learnedmln': learnedmln}
    return jsonify(res)


@mlnApp.app.route('/mln/learning/_change_example', methods=['POST'])
def change_example_lrn():
    data = json.loads(request.get_data())
    return change_example("learning", data['folder'])
