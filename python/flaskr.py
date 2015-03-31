from datetime import timedelta
from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, make_response, current_app, stream_with_context, Response
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

DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

#change static folder to 'resource' for qooxdoo
app = Flask(__name__, static_folder='resource')
app.config.from_object(__name__)

#data
numEngine = 0;
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

@app.route('/')
def show_entries():
    return render_template('index.html', **locals())

@app.route('/_change_engine', methods=['GET', 'OPTIONS'])
def change_engine():
		
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

		# change additional parameters
		params = settings.get("params%d" % int(numEngine), "")

		# change selected inference methods
		preferedMethod = settings.get("method%d" % int(numEngine), methods[0])
		#if preferedMethod not in methods: preferedMethod = methods[0]
		
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
		return text
@app.route('/_test', methods=['GET', 'OPTIONS'])
def test():
	return "LOL"

@app.route('/_start_inference', methods=['GET', 'OPTIONS'])
def start_inference():
	emln = request.args['emln']
        mln = request.args['mln']
        emln = request.args['emln']
        db = request.args['db']
        #qf = self.selected_qf.get()
        mln_text = request.args['mln_text']
        db_text = request.args['db_text']
        #qf_text = self.selected_qf.get_text()
        output = request.args['output']
        method = request.args['method']
        params = request.args['params']
        # update settings
        settings["mln"] = mln
        settings["mln_rename"] = request.args['mln_rename_on_edit']
        settings["db"] = db
        settings["db_rename"] = request.args['db_rename_on_edit']
        settings["method%d" % int(numEngine)] = method
        settings["params%d" % int(numEngine)] = params
        settings["query"] = request.args.get('query')
        settings["queryByDB"][db] = settings["query"]
        settings["emlnByDB"][db] = emln
        settings["engine"] = request.args['engine']
        #settings["qf"] = qf
        settings["output_filename"] = output
        settings["closedWorld"] = request.args['closed_world']
        settings["cwPreds"] = request.args['cw_preds']
        settings["convertAlchemy"] = request.args['convert_to_alchemy']
        settings["useEMLN"] = request.args['use_emln']
        settings["maxSteps"] = request.args['max_steps']
        settings["numChains"] = request.args['num_chains']
        settings['logic'] = request.args['logic']
        settings['grammar'] = request.args['grammar']
        settings['useMultiCPU'] = request.args['use_multicpu']

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
        pickle.dump(settings, file(configname, "w+"))
        
        # some information
        #print "\n--- query ---\n%s" % self.settings["query"]        
        #print "\n--- evidence (%s) ---\n%s" % (db, db_text.strip())
        # MLN input files
        input_files = [mln]
        if settings["useEMLN"] == 1 and emln != "": # using extended model
            input_files.append(emln)
        # hide main window
        #self.master.withdraw()
        
        # runinference
        try:
            inference.run(input_files, db, method, settings["query"], params=params, **settings)
        except:
            cls, e, tb = sys.exc_info()
            sys.stderr.write("Error: %s\n" % str(e))
	    return ("Error: %s\n" % str(e))
            traceback.print_tb(tb)
        # restore main window
        #self.master.deiconify()
        #self.setGeometry()
        # reload the files (in case they changed)
        #self.selected_mln.reloadFile()
        #self.selected_db.reloadFile()

        sys.stdout.flush()
	return "LOL"


@app.route('/_init', methods=['GET', 'OPTIONS'])
def init_options():
    return ';'.join(((','.join(alchemy_engines)),(','.join(inference_methods)),(','.join(files)),(',,'.join(dbs)),(settings["query"]),(settings["maxSteps"])))

if __name__ == '__main__':
# read previously saved settings
    settings = {}
    confignames = ["mlnquery.config.dat", "query.config.dat"]
    for filename in confignames:
        configname = filename
        if os.path.exists(configname):
            try:
                settings = pickle.loads("\n".join(map(lambda x: x.strip("\r\n"), file(configname, "r").readlines())))
            except:
                pass
            break
    app.run(debug=True)

    
   
