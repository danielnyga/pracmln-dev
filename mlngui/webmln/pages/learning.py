from webmln.mlninit import mlnApp

from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response, current_app, stream_with_context, Response,\
     send_from_directory
import os
import sys
import pickle
import configMLN as config
from mln.methods import InferenceMethods
from mlnQueryTool import MLNInfer
from fnmatch import fnmatch
from multiprocessing.queues import Queue
import subprocess

#
import logging
import traceback
from mln import readMLNFromFile
from mln.util import balancedParentheses
from mln.database import readDBFromFile

DEBUG = False
SECRET_KEY = 'secret'
USERNAME = 'admin'
PASSWORD = 'default'

numEngine = 0

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

@mlnApp.app.route('/mln/_change_engine', methods=['GET', 'OPTIONS'])
def change_engine():
        global numEngine
        engineName = request.args.get('engine')
        if engineName in ("internal", "PRACMLNs"):
            numEngine = 1
            methods = inference.pymlns_methods
            #self.cb_save_results.configure(state=NORMAL)
        elif engineName == "J-MLNs":
            numEngine = 2
            methods = inference.jmlns_methods.keys()
            #self.cb_closed_world.configure(state=DISABLED)
            #self.cb_save_results.configure(state=NORMAL)
        else:
            numEngine = 0
            methods = inference.alchemy_methods.keys()
            #self.cb_closed_world.configure(state=NORMAL)
            #self.cb_save_results.configure(state=DISABLED)

        params = settings.get("params%d" % int(numEngine), "")

        preferedMethod = settings.get("method%d" % int(numEngine), methods[0])
        return ';'.join((params,preferedMethod,','.join(methods)))

@mlnApp.app.route('/mln/_mln', methods=['GET', 'OPTIONS'])
def fetch_mln():
        filename = request.args.get('filename')
        directory = '.'
        if os.path.exists(os.path.join(directory, filename)):
            text = file(os.path.join(directory, filename)).read()
            if text.strip() == "":
                text = "// %s is empty\n" % filename;
        else:
            text = filename
        return text

@mlnApp.app.route('/mln/_load_evidence', methods=['GET', 'OPTIONS'])
def load_evidence():
        filename = request.args.get('filename')
        directory = '.'
        if os.path.exists(os.path.join(directory, filename)):
            text = file(os.path.join(directory, filename)).read()
            if text.strip() == "":
                text = "// %s is empty\n" % filename;
        else:
            text = filename
        query = settings["queryByDB"].get(filename)
        return ';'.join((text,query))

@mlnApp.app.route('/mln/_test', methods=['GET', 'OPTIONS'])
def test():
    return "LOL"

class StdoutQueue(Queue):
    def __init__(self,*args,**kwargs):
        Queue.__init__(self,*args,**kwargs)

    def write(self,msg):
        self.put(msg)

    def flush(self):
        sys.__stdout__.flush()

@mlnApp.app.route('/mln/_start_inference', methods=['GET', 'OPTIONS'])
def start_inference():

    if not "queryByDB" in settings: settings["queryByDB"] = {}
    if not "emlnByDB" in settings: settings["emlnByDB"] = {}
    if not "use_multiCPU" in settings: settings['use_multiCPU'] = False
    emln = request.args['emln'].encode('ascii','ignore')
    mln = request.args['mln'].encode('ascii','ignore')
    emln = request.args['emln'].encode('ascii','ignore')
    db = request.args['db'].encode('ascii','ignore')
    #qf = self.selected_qf.get()
    mln_text = request.args['mln_text'].encode('ascii','ignore')
    db_text = request.args['db_text'].encode('ascii','ignore')
    #qf_text = self.selected_qf.get_text()
    output = request.args['output'].encode('ascii','ignore')
    method = request.args['method'].encode('ascii','ignore')
    params = request.args['params'].encode('ascii','ignore')
    # update settings
    settings["mln"] = mln
    settings["mln_rename"] = convert_to_boolean(request.args["mln_rename_on_edit"])
    settings["db"] = db
    settings["db_rename"] = convert_to_boolean(request.args['db_rename_on_edit'])
    settings["method%d" % int(numEngine)] = method
    settings["params%d" % int(numEngine)] = params
    settings["query"] = request.args.get('query').encode('ascii','ignore')
    settings["queryByDB"][db] = settings["query"].encode('ascii','ignore')
    #settings["emlnByDB"][db] = emln
    #settings["emlnByDB"][db] = "(no ['*.emln'] files found)"
    settings["engine"] = request.args['engine'].encode('ascii','ignore')
    #settings["qf"] = ''
    settings["output_filename"] = 'smoking-test-pybpll.smoking-train-smoking.results'
    settings["closedWorld"] = convert_to_boolean(request.args['closed_world'])
    settings["cwPreds"] = request.args['cw_preds'].encode('ascii','ignore')
    settings["convertAlchemy"] = convert_to_boolean(request.args['convert_to_alchemy'])
    settings["useEMLN"] = convert_to_boolean(request.args['use_emln'])
    settings["maxSteps"] = request.args['max_steps'].encode('ascii','ignore')
    settings["numChains"] = request.args['num_chains'].encode('ascii','ignore')
    settings['logic'] = request.args['logic'].encode('ascii','ignore')
    settings['grammar'] = request.args['grammar'].encode('ascii','ignore')
    settings['useMultiCPU'] = convert_to_boolean(request.args['use_multicpu'])
    if "params" in settings: del settings["params"]
    #if saveGeometry:
    #    settings["geometry"] = self.master.winfo_geometry()
    #self.settings["saveResults"] = save_results.get()
    # write query to file
    write_query_file = False
    if write_query_file:
        query_file = "%s.query" % db
        f = file(query_file, "w")
        f.write(settings["query"])
        f.close()
    # write settings
    #pickle.dump(settings, file(configname, "w+"))

    # some information
    #print "\n--- query ---\n%s" % self.settings["query"]
    #print "\n--- evidence (%s) ---\n%s" % (db, db_text.strip())
    # MLN input files
    input_files = [mln]
    if settings["useEMLN"] == 1 and emln != "": # using extended model
        input_files.append(emln)

        # runinference

    settings_local = settings
    #params_local = params
    #def worker(q):
    #    sys.stdout = q
    #results = inference.run(input_files, db, method, settings["query"], params=params, **settings)

    #thread.start_new_thread(worker,(q,))

    #def generate(mlnFiles, evidenceDB, method, queries, engine="PRACMLNs", output_filename=None, params="", **settings):
    def generate():
        queue = StdoutQueue()
        sys.stdout = queue
        sys.stderr = queue
        #yield inference.run(input_files, db, method, settings["query"], params=params, **settings)
        #yield "results:\n"

        #while not q.empty():
	    #    temp = q.get()
	    #    temp = temp.replace("\033[1m","")
	    #    temp = temp.replace("\033[0m","")
        #        yield temp
            #key, value = shitfuck.popitem()
            #yield "{:.6f}".format(value) + " " + key + "\n"
        # reload the files (in case they changed)
        #self.selected_mln.reloadFile()
        #self.selected_db.reloadFile()

        #sys.stdout.flush()
        pymlns_methods = InferenceMethods.getNames()
        alchemy_methods = {"MC-SAT":"-ms", "Gibbs sampling":"-p", "simulated tempering":"-simtp", "MaxWalkSAT (MPE)":"-a", "belief propagation":"-bp"}
        jmlns_methods = {"MaxWalkSAT (MPE)":"-mws", "MC-SAT":"-mcsat", "Toulbar2 B&B (MPE)":"-t2"}
        alchemy_versions = config.alchemy_versions
        default_settings = {"numChains":"1", "maxSteps":"", "saveResults":False, "convertAlchemy":False, "openWorld":True} # a minimal set of settings required to run inference

        settings = dict(default_settings)
        settings.update(settings_local)
        params_local = params
        method_local = method
        input_files_local = input_files
        db_local = db
        query = settings['query']

        results_suffix = ".results"
        output_base_filename = settings['output_filename']
        if output_base_filename[-len(results_suffix):] == results_suffix:
            output_base_filename = output_base_filename[:-len(results_suffix)]

        # determine closed-world preds
        cwPreds = []
        if "cwPreds" in settings:
            cwPreds = filter(lambda x: x != "", map(str.strip, settings["cwPreds"].split(",")))
        haveOutFile = False
        results = None

        # collect inference arguments
        args = {"details":True, "shortOutput":True, "debugLevel":1}
        args.update(eval("dict(%s)" % params_local)) # add additional parameters
        # set the debug level
        logging.getLogger().setLevel(eval('logging.%s' % args.get('debug', 'WARNING').upper()))

        if settings["numChains"] != "":
            args["numChains"] = int(settings["numChains"])
        if settings["maxSteps"] != "":
            args["maxSteps"] = int(settings["maxSteps"])
        outFile = None
        if settings["saveResults"]:
            haveOutFile = True
            outFile = file(settings['output_filename'], "w")
            args["outFile"] = outFile
        args['useMultiCPU'] = settings.get('useMultiCPU', False)
        args["probabilityFittingResultFileName"] = output_base_filename + "_fitted.mln"

        print args
        # engine-specific handling
        if settings['engine'] in ("internal", "PRACMLNs"):
            try:
                print "\nStarting %s...\n" % method_local
                # create MLN
                mln = readMLNFromFile(input_files_local, logic=settings['logic'], grammar=settings['grammar'])#, verbose=verbose, defaultInferenceMethod=MLN.InferenceMethods.byName(method))
                mln.defaultInferenceMethod = InferenceMethods.byName(method_local)

                # read queries and check them for correct syntax. collect all the query predicates
                # in case the closedWorld flag is set
                queries = []
                queryPreds = set()
                q = ""
                for s in map(str.strip, query.split(",")):
                    if q != "": q += ','
                    q += s
                    if balancedParentheses(q):
                        try:
                            # try to read it as a formula and update query predicates
                            f = mln.logic.parseFormula(q)
                            literals = f.iterLiterals()
                            predNames = map(lambda l: l.predName, literals)
                            queryPreds.update(predNames)
                        except:
                            # not a formula, must be a pure predicate name
                            queryPreds.add(s)
                        queries.append(q)
                        q = ""
                if q != "": raise Exception("Unbalanced parentheses in queries: " + q)

                # set closed-world predicates
                if settings.get('closedWorld', False):
                    mln.setClosedWorldPred(*set(mln.predicates.keys()).difference(queryPreds))
                else:
                    mln.setClosedWorldPred(*cwPreds)

                # parse the database
                dbs = readDBFromFile(mln, db_local)
                if len(dbs) != 1:
                    raise Exception('Only one database is supported for inference.')
                db_local = dbs[0]

                # create ground MRF
                mln = mln.materializeFormulaTemplates([db_local], args.get('verbose', False))
                mrf = mln.groundMRF(db_local, verbose=args.get('verbose', False), groundingMethod='FastConjunctionGrounding')



                yield(';'.join(mrf.gndAtoms))
                yield(';;')
                yield(';'.join(str(i[1]) for i in mrf.getGroundFormulas()))
                yield(';;')
                #mrf.printGroundAtoms()
                #mrf.printGroundFormulas()
                # check for print/write requests
                if "printGroundAtoms" in args:
                    if args["printGroundAtoms"]:
                        mrf.printGroundAtoms()
                if "printGroundFormulas" in args:
                    if args["printGroundFormulas"]:
                        mrf.printGroundFormulas()
                if "writeGraphML" in args:
                    if args["writeGraphML"]:
                        graphml_filename = output_base_filename + ".graphml"
                        print "writing ground MRF as GraphML to %s..." % graphml_filename
                        mrf.writeGraphML(graphml_filename)
                # invoke inference and retrieve results
                print 'Inference parameters:', args
                mrf.mln.watch.tag('Inference')
                dist = mrf.infer(queries, **args)
                #mrf.printGroundAtoms()
                #mrf.printGroundFormulas()
                results = {}
                fullDist = args.get('fullDist', False)
                if fullDist:
                    pickle.dump(dist, open('%s.dist' % output_base_filename, 'w+'))
                else:
                    for gndFormula, p in mrf.getResultsDict().iteritems():
                        results[str(gndFormula)] = p
                yield(';'.join(results.keys()))
                yield(';;')
                yield(';'.join(map(str,results.values())))
                mrf.mln.watch.printSteps()
                # close output file and open if requested
                if outFile != None:
                    outFile.close()
            except:
                cls, e, tb = sys.exc_info()
                sys.stderr.write("Error: %s\n" % str(e))
                traceback.print_tb(tb)

        yield(';;')
        while not queue.empty():
	        temp = queue.get()
	        temp = temp.replace("\033[1m","")
	        temp = temp.replace("\033[0m","")
                yield temp
    #return Response(stream_with_context(generate(input_files, db, method, settings["query"], params=params, **settings)))
    return Response(generate())

@mlnApp.app.route('/mln/_use_model_ext', methods=['GET', 'OPTIONS'])
def get_emln():
    emlns = []
    for filename in os.listdir('.'):
        if fnmatch(filename, '*.emln'):
            emlns.append(filename)
    emlns.sort()
    if len(emlns) == 0: emlns.append("(no %s files found)" % str('*.emln'))
    return ','.join(emlns)

@mlnApp.app.route('/mln/_init', methods=['GET', 'OPTIONS'])
def init_options():
    return ';'.join(((','.join(alchemy_engines)),(','.join(inference_methods)),(','.join(files)),(',,'.join(dbs)),(settings["query"]),(settings["maxSteps"])))


def initialize():
    global settings
    global inference
    global inference_methods
    global params
    global files
    global dbs
    global alchemy_engines

    settings = {}
    alchemy_engines = config.alchemy_versions.keys()
    alchemy_engines.sort()
    inference = MLNInfer()
    inference_methods = InferenceMethods.getNames()
    params = ""
    files = []
    dbs = []
    for filename in os.listdir('.'):
        if fnmatch(filename, '*.mln'):
                files.append(filename)
        if fnmatch(filename, '*.db') or fnmatch(filename, '*.blogdb'):
            dbs.append(filename)
    files.sort()
    dbs.sort()
    if len(files) == 0: files.append("(no %s files found)" % str('*.mln'))
    if len(dbs) == 0: dbs.append("(no %s files found)" % str('[\'*.db\',\'*.blogdb\']'))
    confignames = ["mlnquery.config.dat", "query.config.dat"]
    for filename in confignames:
        configname = filename
        if os.path.exists(configname):
            try:
                settings = pickle.loads("\n".join(map(lambda x: x.strip(
                    "\r\n"), file(configname, "r").readlines())))
            except:
                pass
            break

def convert_to_boolean(request):
    if request == u'true':
        result = 1
    else:
        result = 0
    return result
