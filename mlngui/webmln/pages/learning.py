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
from mln.methods import InferenceMethods
from mlnQueryTool import MLNInfer


#
import logging
import traceback
from mln import readMLNFromFile
from mln.util import balancedParentheses
from mln.database import readDBFromFile
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

    return jsonify( {'text': text} )

@mlnApp.app.route('/mln/_test', methods=['GET', 'OPTIONS'])
def test():
    return "LOL"

@mlnApp.app.route('/mln/_change_example', methods=['POST'])
def change_example():
    mlnsession = ensure_mln_session(session)
    data = json.loads(request.get_data())
    mlnsession.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], data['folder'])
    log.info(mlnsession.xmplFolder)
    mlnFiles, dbs = getExampleFiles(mlnsession.xmplFolder)
    log.info(dbs)
    log.info(mlnFiles)

    return jsonify( {'dbs': dbs, 'mlns': mlnFiles} )


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
    log.info(data)

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

    try:
        # expand the parameters
        params = settings
        if 'params' in params:
            params.update(eval("dict(%s)" % params['params']))
            del params['params']
        # create the MLN and evidence database and the parse the queries
        modelstr = mln_content + (emln_content if settings['use_emln'] not in (None, '') and emln_content != '' else '')
        mln = parse_mln(modelstr, searchPath=mlnsession.xmplFolder, logic=settings['logic'], grammar=settings['grammar'])
        db = parse_db(mln, db_content, ignore_unknown_preds=params.get('ignore_unknown_preds', False))
        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        else:
            db = db[0]
        # parse non-atomic params
        queries = parse_queries(mln, str(settings['queries']))
        cw_preds = filter(lambda x: x != "", map(str.strip, str(params["cw_preds"].split(",")))) if 'cw_preds' in params else []
        if settings['cw']:
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
            log.info('INFERENCE RESULTS')
            inference.write()
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

    # if "params" in settings: del settings["params"]
    # #if saveGeometry:
    # #    settings["geometry"] = self.master.winfo_geometry()
    # #self.settings["saveResults"] = save_results.get()
    # # write query to file
    # write_query_file = False
    # if write_query_file:
    #     query_file = "%s.query" % db
    #     f = file(query_file, "w")
    #     f.write(settings["query"])
    #     f.close()
    # # write settings
    # #pickle.dump(settings, file(configname, "w+"))
    #
    # # some information
    # #print "\n--- query ---\n%s" % self.settings["query"]
    # #print "\n--- evidence (%s) ---\n%s" % (db, db_text.strip())
    # # MLN input files
    # input_files = [mln]
    # if settings["useEMLN"] == 1 and emln != "": # using extended model
    #     input_files.append(emln)
    #
    #     # runinference
    #
    # settings_local = settings
    # #params_local = params
    # #def worker(q):
    # #    sys.stdout = q
    # #results = inference.run(input_files, db, method, settings["query"], params=params, **settings)
    #
    # #thread.start_new_thread(worker,(q,))
    #
    #
    # #def generate(mlnFiles, evidenceDB, method, queries, engine="PRACMLNs", output_filename=None, params="", **settings):
    # def generate():
    #     log.info('generate')
    #     atoms = []
    #     formulas = []
    #     resultKeys = []
    #     resultValues = []
    #     output = ''
    #
    #     queue = StdoutQueue()
    #     sys.stdout = queue
    #     sys.stderr = queue
    #
    #     #while not q.empty():
	 #    #    temp = q.get()
	 #    #    temp = temp.replace("\033[1m","")
	 #    #    temp = temp.replace("\033[0m","")
    #     #        yield temp
    #         #key, value = shitfuck.popitem()
    #         #yield "{:.6f}".format(value) + " " + key + "\n"
    #     # reload the files (in case they changed)
    #     #self.selected_mln.reloadFile()
    #     #self.selected_db.reloadFile()
    #
    #     default_settings = {"numChains":"1", "maxSteps":"", "saveResults":False, "openWorld":True} # a minimal set of settings required to run inference
    #
    #     settings = dict(default_settings)
    #     settings.update(settings_local)
    #     params_local = params
    #     method_local = method
    #     input_files_local = input_files
    #     db_local = db
    #     query = settings['query']
    #
    #     results_suffix = ".results"
    #     output_base_filename = settings['output_filename']
    #     if output_base_filename[-len(results_suffix):] == results_suffix:
    #         output_base_filename = output_base_filename[:-len(results_suffix)]
    #
    #     # determine closed-world preds
    #     cwPreds = []
    #     if "cwPreds" in settings:
    #         cwPreds = filter(lambda x: x != "", map(str.strip, settings["cwPreds"].split(",")))
    #     haveOutFile = False
    #     results = None
    #
    #     # collect inference arguments
    #     args = {"details":True, "shortOutput":True, "debugLevel":1}
    #     args.update(eval("dict(%s)" % params_local)) # add additional parameters
    #     # set the debug level
    #     logging.getLogger().setLevel(eval('logging.%s' % args.get('debug', 'WARNING').upper()))
    #
    #     if settings["numChains"] != "":
    #         args["numChains"] = int(settings["numChains"])
    #     if settings["maxSteps"] != "":
    #         args["maxSteps"] = int(settings["maxSteps"])
    #     outFile = None
    #     if settings["saveResults"]:
    #         haveOutFile = True
    #         outFile = file(settings['output_filename'], "w")
    #         args["outFile"] = outFile
    #     args['useMultiCPU'] = settings.get('useMultiCPU', False)
    #     args["probabilityFittingResultFileName"] = output_base_filename + "_fitted.mln"
    #
    #     # engine-specific handling
    #     if settings['engine'] in ("internal", "PRACMLNs"):
    #         try:
    #             print "\nStarting %s...\n" % method_local
    #             # create MLN
    #             mln = readMLNFromFile(input_files_local, logic=settings['logic'], grammar=settings['grammar'])#, verbose=verbose, defaultInferenceMethod=MLN.InferenceMethods.byName(method))
    #             mln.defaultInferenceMethod = InferenceMethods.byName(method_local)
    #
    #             # read queries and check them for correct syntax. collect all the query predicates
    #             # in case the closedWorld flag is set
    #             queries = []
    #             queryPreds = set()
    #             q = ""
    #             for s in map(str.strip, query.split(",")):
    #                 if q != "": q += ','
    #                 q += s
    #                 if balancedParentheses(q):
    #                     try:
    #                         # try to read it as a formula and update query predicates
    #                         f = mln.logic.parseFormula(q)
    #                         literals = f.iterLiterals()
    #                         predNames = map(lambda l: l.predName, literals)
    #                         queryPreds.update(predNames)
    #                     except:
    #                         # not a formula, must be a pure predicate name
    #                         queryPreds.add(s)
    #                     queries.append(q)
    #                     q = ""
    #             if q != "": raise Exception("Unbalanced parentheses in queries: " + q)
    #
    #             # set closed-world predicates
    #             if settings.get('closedWorld', False):
    #                 mln.setClosedWorldPred(*set(mln.predicates.keys()).difference(queryPreds))
    #             else:
    #                 mln.setClosedWorldPred(*cwPreds)
    #
    #             # parse the database
    #             dbs = readDBFromFile(mln, db_local)
    #             if len(dbs) != 1:
    #                 raise Exception('Only one database is supported for inference.')
    #             db_local = dbs[0]
    #
    #             # create ground MRF
    #             mln = mln.materializeFormulaTemplates([db_local], args.get('verbose', False))
    #             mrf = mln.groundMRF(db_local, verbose=args.get('verbose', False), groundingMethod='FastConjunctionGrounding')
    #
    #
    #             atoms = mrf.gndAtoms.keys()
    #             formulas = [str(i[1]) for i in mrf.getGroundFormulas()]
    #             #mrf.printGroundAtoms()
    #             #mrf.printGroundFormulas()
    #             # check for print/write requests
    #             if "printGroundAtoms" in args:
    #                 if args["printGroundAtoms"]:
    #                     mrf.printGroundAtoms()
    #             if "printGroundFormulas" in args:
    #                 if args["printGroundFormulas"]:
    #                     mrf.printGroundFormulas()
    #             if "writeGraphML" in args:
    #                 if args["writeGraphML"]:
    #                     graphml_filename = output_base_filename + ".graphml"
    #                     print "writing ground MRF as GraphML to %s..." % graphml_filename
    #                     mrf.writeGraphML(graphml_filename)
    #             # invoke inference and retrieve results
    #             print 'Inference parameters:', args
    #             mrf.mln.watch.tag('Inference')
    #             dist = mrf.infer(queries, **args)
    #             #mrf.printGroundAtoms()
    #             #mrf.printGroundFormulas()
    #             results = {}
    #             fullDist = args.get('fullDist', False)
    #             if fullDist:
    #                 pickle.dump(dist, open('%s.dist' % output_base_filename, 'w+'))
    #             else:
    #                 for gndFormula, p in mrf.getResultsDict().iteritems():
    #                     results[str(gndFormula)] = p
    #
    #             resultKeys = results.keys()
    #             resultValues = results.values()
    #             mrf.mln.watch.printSteps()
    #             # close output file and open if requested
    #             if outFile != None:
    #                 outFile.close()
    #         except:
    #             cls, e, tb = sys.exc_info()
    #             sys.stderr.write("Error: %s\n" % str(e))
    #             traceback.print_tb(tb)
    #
    #     while not queue.empty():
	 #        temp = queue.get()
	 #        temp = temp.replace("\033[1m","")
	 #        temp = temp.replace("\033[0m","")
    #             output = temp
    #     return {'atoms': atoms, 'formulas': formulas, 'resultkeys': resultKeys, 'resultvalues': resultValues, 'output': output}
    # #return Response(stream_with_context(generate(input_files, db, method, settings["query"], params=params, **settings)))
    # # return Response(generate())
    # res = generate()
    # print res
    # return jsonify( res )

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
            'queries': mlnsession.settings['query'],
            'maxSteps': mlnsession.settings['maxSteps'],
            'examples': dirs}
    return jsonify( res )


def initialize():
    log.info('initialize')
    mlnsession = ensure_mln_session(session)
    mlnsession.inference = MLNInfer()
    mlnsession.xmplFolder = os.path.join(mlnApp.app.config['EXAMPLES_FOLDER'], DEFAULT_EXAMPLE)
    mlnsession.params = ''

    confignames = ["mlnquery.config.dat", "query.config.dat"]
    settings = {}
    for filename in confignames:
        configname = filename
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
