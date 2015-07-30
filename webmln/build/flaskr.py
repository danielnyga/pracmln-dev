from datetime import timedelta
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response, current_app, stream_with_context, Response,\
     send_from_directory
from functools import update_wrapper
import os
import sys
import json
import pickle
import fnmatch
import shlex
import time
import configMLN as config
from mln.methods import InferenceMethods
from mlnQueryTool import MLNInfer
from fnmatch import fnmatch
from multiprocessing.queues import Queue
import thread
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

#change static folder to 'resource' for qooxdoo
app = Flask(__name__, static_folder='build')
app.config.from_object(__name__)

def call(args):
    try:
        subprocess.call(args)
    except:
        args = list(args)
        args[0] = args[0] + ".bat"
        subprocess.call(args)

#data

@app.route('/')
def show_entries():
    return send_from_directory(app.root_path, 'index.html')

@app.route('/<path:filename>')
def download_static(filename):
    return send_from_directory(app.root_path, filename)

@app.route('/_change_engine', methods=['GET', 'OPTIONS'])
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

@app.route('/_mln', methods=['GET', 'OPTIONS'])
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

@app.route('/_load_evidence', methods=['GET', 'OPTIONS'])
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
@app.route('/_test', methods=['GET', 'OPTIONS'])
def test():
    return "LOL"

class StdoutQueue(Queue):
    def __init__(self,*args,**kwargs):
        Queue.__init__(self,*args,**kwargs)

    def write(self,msg):
        self.put(msg)

    def flush(self):
        sys.__stdout__.flush()

@app.route('/_start_inference', methods=['GET', 'OPTIONS'])
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
                
        elif settings['engine'] == "J-MLNs": # engine is J-MLNs (ProbCog's Java implementation)
            
            # create command to execute
            app = "MLNinfer"
            params_local = [app, "-i", ",".join(input_files_local), "-e", db_local, "-q", query, jmlns_methods[method_local]] + shlex.split(params_local)
            if settings["saveResults"]:
                params_local += ["-r", output_filename]
            if settings["maxSteps"] != "":
                params_local += ["-maxSteps", settings["maxSteps"]]
            if len(cwPreds) > 0:
                params_local += ["-cw", ",".join(cwPreds)]
            outFile = None
            if settings["saveResults"]:
                outFile = settings['output_filename']
                params_local += ["-r", outFile]
            
            # execute
            params_local = map(str, params_local)
            print "\nStarting J-MLNs..."
            print "\ncommand:\n%s\n" % " ".join(params_local)
            t_start = time.time()
            call(params_local)
            t_taken = time.time() - t_start
            
            if outFile is not None:
                results = dict(readAlchemyResults(outFile))
        
        else: # engine is Alchemy
            haveOutFile = True
            infile = input_files_local[0]
            mlnObject = None
            # explicitly convert MLN to Alchemy format, i.e. resolve weights that are arithm. expressions (on request) -> create temporary file
            if settings["convertAlchemy"]:
                print "\n--- temporary MLN ---\n"
                mlnObject = mln.MLN(input_files_local)
                infile = input_files_local[0]
                infile = infile[:infile.rfind(".")]+".alchemy.mln"
                f = file(infile, "w")
                mlnObject.write(f)
                f.close()
                mlnObject.write(sys.stdout)
                input_files_local = [infile]
                print "\n---"
            # get alchemy version-specific data
            alchemy_version = alchemy_versions[settings['engine']]
            if type(alchemy_version) != dict:
                alchemy_version = {"path": str(alchemy_version)}
            usage = config.default_infer_usage
            if "usage" in alchemy_version:
                usage = alchemy_version["usage"]
            # find alchemy binary
            path = alchemy_version["path"]
            path2 = os.path.join(path, "bin")
            if os.path.exists(path2):
                path = path2
            alchemyInfer = os.path.join(path, "infer")
            if not os.path.exists(alchemyInfer) and not os.path.exists(alchemyInfer+".exe"):
                error = "Alchemy's infer/infer.exe binary not found in %s. Please configure Alchemy in python/configMLN.py" % path
                #tkMessageBox.showwarning("Error", error)
                raise Exception(error)
            # parse additional parameters for input files
            add_params = shlex.split(params_local)
            i = 0
            while i < len(add_params):
                if add_params[i] == "-i":
                    input_files_local.append(add_params[i+1])
                    del add_params[i]
                    del add_params[i]
                    continue
                i += 1
            # create command to execute
            if settings['output_filename'] is None: raise Exception("For Alchemy, provide an output filename!")            
            params_local = [alchemyInfer, "-i", ",".join(input_files_local), "-e", db_local, "-q", query, "-r", settings['output_filename'], alchemy_methods[method_local]] + add_params            
            if settings["numChains"] != "":
                params_local += [usage["numChains"], settings["numChains"]]
            if settings["maxSteps"] != "":
                params_local += [usage["maxSteps"], settings["maxSteps"]]
            owPreds = []
            if settings["openWorld"]:
                print "\nFinding predicate names..."
                #doesn't work
                preds = mln_local.getPredicateList(infile)
                owPreds = filter(lambda x: x not in cwPreds, preds)
                params_local += [usage["openWorld"], ",".join(owPreds)]
            if len(cwPreds) > 0:
                params_local += ["-cw", ",".join(cwPreds)]
            # remove old output file (if any)
            if os.path.exists(settings['output_filename']):
                os.remove(settings['output_filename'])
                pass
            # execute
            params_local = map(str, params_local)
            print "\nStarting Alchemy..."
            command = subprocess.list2cmdline(params_local)
            print "\ncommand:\n%s\n" % " ".join(params_local)
            t_start = time.time()
            call(params_local)
            t_taken = time.time() - t_start
            # print results file
            if True:
                print "\n\n--- output ---\n"
                results = dict(readAlchemyResults(settings['output_filename']))
                for atom, prob in results.iteritems():
                    print "%.4f  %s" % (prob, atom)                    
                print "\n"
            # append information on query and mln to results file
            f = file(settings['output_filename'], "a")
            dbfile = file(db_local, "r")
            db_text = dbfile.read()
            dbfile.close()
            infile = file(infile, "r")
            mln_text = infile.read()
            infile.close()
            f.write("\n\n/*\n\n--- command ---\n%s\n\n--- evidence ---\n%s\n\n--- mln ---\n%s\ntime taken: %fs\n\n*/" % (command, db_text.strip(), mln_text.strip(), t_taken))
            f.close()
            # delete temporary mln
            if settings["convertAlchemy"] and not config_value("keep_alchemy_conversions", True):
                os.unlink(infile)
        yield(';;')
        while not queue.empty():
	        temp = queue.get()
	        temp = temp.replace("\033[1m","")
	        temp = temp.replace("\033[0m","")
                yield temp
    #return Response(stream_with_context(generate(input_files, db, method, settings["query"], params=params, **settings)))
    return Response(generate())

@app.route('/_use_model_ext', methods=['GET', 'OPTIONS'])
def get_emln():
    emlns = []
    for filename in os.listdir('.'):
        if fnmatch(filename, '*.emln'):
            emlns.append(filename)
    emlns.sort()
    if len(emlns) == 0: emlns.append("(no %s files found)" % str('*.emln'))
    return ','.join(emlns)    

@app.route('/_init', methods=['GET', 'OPTIONS'])
def init_options():
    return ';'.join(((','.join(alchemy_engines)),(','.join(inference_methods)),(','.join(files)),(',,'.join(dbs)),(settings["query"]),(settings["maxSteps"])))

def convert_to_boolean(request):
    if request == u'true':
        result = 1
    else:
        result = 0
    return result

if __name__ == '__main__':
    # read previously saved settings
    settings = {}
    alchemy_engines = config.alchemy_versions.keys()
    alchemy_engines.sort()
    inference_methods = InferenceMethods.getNames()
    inference = MLNInfer()
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
                    settings = pickle.loads("\n".join(map(lambda x: x.strip("\r\n"), file(configname, "r").readlines())))
                except:
                    pass
                break
    app.run(debug=False,threaded=True)
