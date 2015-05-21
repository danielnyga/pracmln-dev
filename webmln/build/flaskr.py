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
import configMLN as config
from mln.methods import InferenceMethods
from mlnQueryTool import MLNInfer
from fnmatch import fnmatch
from multiprocessing.queues import Queue
import thread

#
import logging
import traceback
from mln import readMLNFromFile
from mln.util import balancedParentheses
from mln.database import readDBFromFile

DEBUG = False
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

numEngine = 0

#change static folder to 'resource' for qooxdoo
app = Flask(__name__, static_folder='resource')
app.config.from_object(__name__)

#data


@app.route('/')
def show_entries():
    return send_from_directory(app.root_path, 'index.html')

@app.route('/<path:filename>')
def send_static(filename):
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
    q = StdoutQueue()
    sys.stdout = q
    #sys.stderr = q

    #def worker(q):
    #    sys.stdout = q
    results = inference.run(input_files, db, method, settings["query"], params=params, **settings)    

    #thread.start_new_thread(worker,(q,))    

    def generate():
            
        #yield inference.run(input_files, db, method, settings["query"], params=params, **settings)
        #yield "results:\n"
            
        while not q.empty():
	        temp = q.get()
	        temp = temp.replace("\033[1m","")
	        temp = temp.replace("\033[0m","")
                yield temp
            #key, value = shitfuck.popitem()
            #yield "{:.6f}".format(value) + " " + key + "\n"
        # reload the files (in case they changed)
        #self.selected_mln.reloadFile()
        #self.selected_db.reloadFile()

        #sys.stdout.flush()
    return Response(stream_with_context(generate()))

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
