#!/usr/bin/python
# -*- coding: utf-8 -*-

# MLN Query Tool
#
# (C) 2012-2015 by Daniel Nyga
#     2006-2011 by Dominik Jain
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from Tkinter import *
import sys
import os
import struct
import time
import re
import pickle
from fnmatch import fnmatch
import traceback
import widgets
# from widgets import *
import configMLN as config
import mln
import tkMessageBox
import subprocess
import shlex
from mln.util import balancedParentheses
from mln import readMLNFromFile
from mln.methods import InferenceMethods
from widgets import FilePickEdit
from logic.grammar import StandardGrammar, PRACGrammar  # @UnusedImport
import logging
from mln.database import readDBFromFile

def config_value(key, default):
    if key in dir(config):
        return eval("config.%s" % key)
    return default

def call(args):
    try:
        subprocess.call(args)
    except:
        args = list(args)
        args[0] = args[0] + ".bat"
        subprocess.call(args)
        
def readAlchemyResults(output):
    f = file(output, "r")
    results = []
    while True:
        l = f.readline().strip().split(" ")
        if len(l) != 2: break
        atom = l[0]
        prob = float(l[1])
        results.append((atom, prob))
    f.close()
    return results

# --- inference class ---

class MLNInfer(object):
    def __init__(self):
        self.pymlns_methods = InferenceMethods.getNames()
        self.alchemy_methods = {"MC-SAT":"-ms", "Gibbs sampling":"-p", "simulated tempering":"-simtp", "MaxWalkSAT (MPE)":"-a", "belief propagation":"-bp"}
        self.jmlns_methods = {"MaxWalkSAT (MPE)":"-mws", "MC-SAT":"-mcsat", "Toulbar2 B&B (MPE)":"-t2"}
        self.alchemy_versions = config.alchemy_versions
        self.default_settings = {"numChains":"1", "maxSteps":"", "saveResults":False, "convertAlchemy":False, "openWorld":True} # a minimal set of settings required to run inference
    
    def run(self, mlnFiles, evidenceDB, method, queries, engine="PRACMLNs", output_filename=None, params="", **settings):
        '''
            runs an MLN inference method with the given parameters
        
            mlnFiles: list of one or more MLN input files
            evidenceDB: name of the MLN database file from which to read evidence data
            engine: either "PyMLNs"/"internal", "J-MLNs" or one of the keys in the configured Alchemy versions (see configMLN.py)
            method: name of the inference method
            queries: comma-separated list of queries
            output_filename (compulsory only when using Alchemy): name of the file to which to save results
                For the internal engine, specify saveResults=True as an additional settings to save the results
            params: additional parameters to pass to inference method. For the internal engine, it is a comma-separated
                list of assignments to parameters (dictionary-type string), for the others it's just a string of command-line
                options to pass on
            settings: additional settings that control the inference process, which are usually set by the GUI (see code)
                
            returns a mapping (dictionary) from ground atoms to probability values.
                For J-MLNs, results are only returned if settings are saved to a file (settings["saveResults"]=True and output_filename given)
        '''
        self.settings = dict(self.default_settings)        
        self.settings.update(settings)
        input_files = mlnFiles
        db = evidenceDB
        query = queries
        
        results_suffix = ".results"
        output_base_filename = output_filename
        if output_base_filename[-len(results_suffix):] == results_suffix:
            output_base_filename = output_base_filename[:-len(results_suffix)]
        
        # determine closed-world preds
        cwPreds = []
        if "cwPreds" in self.settings:            
            cwPreds = filter(lambda x: x != "", map(str.strip, self.settings["cwPreds"].split(",")))
        haveOutFile = False
        results = None
        
        # collect inference arguments
        args = {"details":True, "shortOutput":True, "debugLevel":1}
        args.update(eval("dict(%s)" % params)) # add additional parameters
        # set the debug level
        logging.getLogger().setLevel(eval('logging.%s' % args.get('debug', 'WARNING').upper()))

        if self.settings["numChains"] != "":
            args["numChains"] = int(self.settings["numChains"])
        if self.settings["maxSteps"] != "":
            args["maxSteps"] = int(self.settings["maxSteps"])
        outFile = None
        if self.settings["saveResults"]:
            haveOutFile = True
            outFile = file(output_filename, "w")
            args["outFile"] = outFile
        args['useMultiCPU'] = self.settings.get('useMultiCPU', False)
        args["probabilityFittingResultFileName"] = output_base_filename + "_fitted.mln"

        print args
        # engine-specific handling
        if engine in ("internal", "PRACMLNs"): 
            try:
                print "\nStarting %s...\n" % method
                # create MLN
                mln = readMLNFromFile(input_files, logic=self.settings['logic'], grammar=self.settings['grammar'])#, verbose=verbose, defaultInferenceMethod=MLN.InferenceMethods.byName(method))
                mln.defaultInferenceMethod = InferenceMethods.byName(method)
                
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
                if self.settings.get('closedWorld', False):
                    mln.setClosedWorldPred(*set(mln.predicates.keys()).difference(queryPreds))
                else:
                    mln.setClosedWorldPred(*cwPreds)

                # parse the database
                dbs = readDBFromFile(mln, db)
                if len(dbs) != 1:
                    raise Exception('Only one database is supported for inference.')
                db = dbs[0]
                
                # create ground MRF
                mln = mln.materializeFormulaTemplates([db], args.get('verbose', False))
                mrf = mln.groundMRF(db, verbose=args.get('verbose', False), groundingMethod='FastConjunctionGrounding')

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
                results = {}
                fullDist = args.get('fullDist', False)
                if fullDist:
                    pickle.dump(dist, open('%s.dist' % output_base_filename, 'w+'))
                else:
                    for gndFormula, p in mrf.getResultsDict().iteritems():
                        results[str(gndFormula)] = p
                
                mrf.mln.watch.printSteps()
                
                # close output file and open if requested
                if outFile != None:
                    outFile.close()
            except:
                cls, e, tb = sys.exc_info()
                sys.stderr.write("Error: %s\n" % str(e))
                traceback.print_tb(tb)
                
        elif engine == "J-MLNs": # engine is J-MLNs (ProbCog's Java implementation)
            
            # create command to execute
            app = "MLNinfer"
            params = [app, "-i", ",".join(input_files), "-e", db, "-q", query, self.jmlns_methods[method]] + shlex.split(params)
            if self.settings["saveResults"]:
                params += ["-r", output_filename]
            if self.settings["maxSteps"] != "":
                params += ["-maxSteps", self.settings["maxSteps"]]
            if len(cwPreds) > 0:
                params += ["-cw", ",".join(cwPreds)]
            outFile = None
            if self.settings["saveResults"]:
                outFile = output_filename
                params += ["-r", outFile]
            
            # execute
            params = map(str, params)
            print "\nStarting J-MLNs..."
            print "\ncommand:\n%s\n" % " ".join(params)
            t_start = time.time()
            call(params)
            t_taken = time.time() - t_start
            
            if outFile is not None:
                results = dict(readAlchemyResults(outFile))
        
        else: # engine is Alchemy
            haveOutFile = True
            infile = mlnFiles[0]
            mlnObject = None
            # explicitly convert MLN to Alchemy format, i.e. resolve weights that are arithm. expressions (on request) -> create temporary file
            if self.settings["convertAlchemy"]:
                print "\n--- temporary MLN ---\n"
                mlnObject = mln.MLN(input_files)
                infile = input_files[0]
                infile = infile[:infile.rfind(".")]+".alchemy.mln"
                f = file(infile, "w")
                mlnObject.write(f)
                f.close()
                mlnObject.write(sys.stdout)
                input_files = [infile]
                print "\n---"
            # get alchemy version-specific data
            alchemy_version = self.alchemy_versions[engine]
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
                tkMessageBox.showwarning("Error", error)
                raise Exception(error)
            # parse additional parameters for input files
            add_params = shlex.split(params)
            i = 0
            while i < len(add_params):
                if add_params[i] == "-i":
                    input_files.append(add_params[i+1])
                    del add_params[i]
                    del add_params[i]
                    continue
                i += 1
            # create command to execute
            if output_filename is None: raise Exception("For Alchemy, provide an output filename!")            
            params = [alchemyInfer, "-i", ",".join(input_files), "-e", db, "-q", query, "-r", output_filename, self.alchemy_methods[method]] + add_params            
            if self.settings["numChains"] != "":
                params += [usage["numChains"], self.settings["numChains"]]
            if self.settings["maxSteps"] != "":
                params += [usage["maxSteps"], self.settings["maxSteps"]]
            owPreds = []
            if self.settings["openWorld"]:
                print "\nFinding predicate names..."
                preds = mln.getPredicateList(infile)
                owPreds = filter(lambda x: x not in cwPreds, preds)
                params += [usage["openWorld"], ",".join(owPreds)]
            if len(cwPreds) > 0:
                params += ["-cw", ",".join(cwPreds)]
            # remove old output file (if any)
            if os.path.exists(output_filename):
                os.remove(output_filename)
                pass
            # execute
            params = map(str, params)
            print "\nStarting Alchemy..."
            command = subprocess.list2cmdline(params)
            print "\ncommand:\n%s\n" % " ".join(params)
            t_start = time.time()
            call(params)
            t_taken = time.time() - t_start
            # print results file
            if True:
                print "\n\n--- output ---\n"
                results = dict(readAlchemyResults(output_filename))
                for atom, prob in results.iteritems():
                    print "%.4f  %s" % (prob, atom)                    
                print "\n"
            # append information on query and mln to results file
            f = file(output_filename, "a")
            dbfile = file(db, "r")
            db_text = dbfile.read()
            dbfile.close()
            infile = file(infile, "r")
            mln_text = infile.read()
            infile.close()
            f.write("\n\n/*\n\n--- command ---\n%s\n\n--- evidence ---\n%s\n\n--- mln ---\n%s\ntime taken: %fs\n\n*/" % (command, db_text.strip(), mln_text.strip(), t_taken))
            f.close()
            # delete temporary mln
            if self.settings["convertAlchemy"] and not config_value("keep_alchemy_conversions", True):
                os.unlink(infile)
                
        # open output file in editor
        if False and haveOutFile and config.query_edit_outfile_when_done: # this is mostly useless
            editor = config.editor
            params = [editor, output_filename]
            print 'starting editor: %s' % subprocess.list2cmdline(params)
            subprocess.Popen(params, shell=False)
            
        return results

# --- main gui class ---

class MLNQueryGUI(object):

    def __init__(self, master, dir, settings):
        self.initialized = False
        master.title("MLN Query Tool")

        self.master = master
        self.settings = settings
        if not "queryByDB" in self.settings: self.settings["queryByDB"] = {}
        if not "emlnByDB" in self.settings: self.settings["emlnByDB"] = {}
        if not "use_multiCPU" in self.settings: self.settings['use_multiCPU'] = False 
        
        self.frame = Frame(master)
        self.frame.pack(fill=BOTH, expand=1)
        self.frame.columnconfigure(1, weight=1)

        # engine selection
        row = 0        
        Label(self.frame, text="Engine: ").grid(row=row, column=0, sticky="E")
        alchemy_engines = config.alchemy_versions.keys()
        alchemy_engines.sort()
        engines = ["PRACMLNs", "J-MLNs"]
        engines.extend(alchemy_engines)
        self.selected_engine = StringVar(master)
        engine = self.settings.get("engine")
        if not engine in engines: engine = engines[0]
        self.selected_engine.set(engine)
        self.selected_engine.trace("w", self.onChangeEngine)
        list = apply(OptionMenu, (self.frame, self.selected_engine) + tuple(engines))
        list.grid(row=row, column=1, sticky="NWE")

        # grammar selection
        row += 1
        Label(self.frame, text='Grammar: ').grid(row=row, column=0, sticky='E')
        grammars = ['StandardGrammar', 'PRACGrammar']
        self.selected_grammar = StringVar(master)
        grammar = self.settings.get('grammar')
        if not grammar in grammars: grammar = grammars[0]
        self.selected_grammar.set(grammar)
        self.selected_grammar.trace('w', self.onChangeGrammar)
        l = apply(OptionMenu, (self.frame, self.selected_grammar) + tuple(grammars))
        l.grid(row=row, column=1, sticky='NWE')
        
        # logic selection
        row += 1
        Label(self.frame, text='Logic: ').grid(row=row, column=0, sticky='E')
        logics = ['FirstOrderLogic', 'FuzzyLogic']
        self.selected_logic = StringVar(master)
        logic = self.settings.get('logic')
        if not logic in logics: logic = logics[0]
        self.selected_logic.set(logic)
        self.selected_logic.trace('w', self.onChangeLogic)
        l = apply(OptionMenu, (self.frame, self.selected_logic) + tuple(logics))
        l.grid(row=row, column=1, sticky='NWE')
        
        # mln selection
        row += 1
        Label(self.frame, text="MLN: ").grid(row=row, column=0, sticky=NE)
        self.selected_mln = FilePickEdit(self.frame, config.query_mln_filemask, self.settings.get("mln", ""), 22, self.changedMLN, rename_on_edit=self.settings.get("mln_rename", 0), font=config.fixed_width_font, coloring=config.coloring)
        self.selected_mln.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)
        # option: convert to Alchemy format
        self.convert_to_alchemy = IntVar()
        self.cb_convert_to_alchemy = Checkbutton(self.selected_mln.options_frame, text="convert to Alchemy format", variable=self.convert_to_alchemy)
        self.cb_convert_to_alchemy.pack(side=LEFT)
        self.convert_to_alchemy.set(self.settings.get("convertAlchemy", 0))
        # option: use model extension
        self.use_emln = IntVar()
        self.cb_use_emln = Checkbutton(self.selected_mln.options_frame, text="use model extension", variable=self.use_emln)
        self.cb_use_emln.pack(side=LEFT)
        self.use_emln.set(self.settings.get("useEMLN", 0))
        self.use_emln.trace("w", self.onChangeUseEMLN)
        # mln extension selection
        self.selected_emln = FilePickEdit(self.selected_mln, "*.emln", None, 12, None, rename_on_edit=self.settings.get("mln_rename", 0), font=config.fixed_width_font, coloring=config.coloring)
        self.onChangeUseEMLN()

        # evidence database selection
        row += 1
        Label(self.frame, text="Evidence: ").grid(row=row, column=0, sticky=NE)
        self.selected_db = FilePickEdit(self.frame, config.query_db_filemask, self.settings.get("db", ""), 12, self.changedDB, rename_on_edit=self.settings.get("emln_rename", 0), font=config.fixed_width_font, coloring=config.coloring)
        self.selected_db.grid(row=row,column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # inference method selection
        row += 1
        self.inference = MLNInfer()
        self.list_methods_row = row
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        ## create list in onChangeEngine

        # queries
        row += 1
        Label(self.frame, text="Queries: ").grid(row=row, column=0, sticky=E)
        self.query = StringVar(master)
        self.query.set(self.settings.get("query", "foo"))
        Entry(self.frame, textvariable = self.query).grid(row=row, column=1, sticky="NEW")

        # query formula selection
        #row += 1
        #Label(self.frame, text="Query formulas: ").grid(row=row, column=0, sticky=NE)
        self.selected_qf = FilePickEdit(self.frame, "*.qf", self.settings.get("qf", ""), 6)
        #self.selected_qf.grid(row=row,column=1)

        # max. number of steps
        row += 1
        Label(self.frame, text="Max. steps: ").grid(row=row, column=0, sticky=E)
        self.maxSteps = StringVar(master)
        self.maxSteps.set(self.settings.get("maxSteps", ""))
        self.entry_steps = Entry(self.frame, textvariable = self.maxSteps)
        self.entry_steps.grid(row=row, column=1, sticky="NEW")

        # number of chains
        row += 1
        Label(self.frame, text="Num. chains: ").grid(row=row, column=0, sticky="NE")
        self.numChains = StringVar(master)
        self.numChains.set(self.settings.get("numChains", ""))
        self.entry_chains = Entry(self.frame, textvariable = self.numChains)
        self.entry_chains.grid(row=row, column=1, sticky="NEW")

        # additional parameters
        row += 1
        Label(self.frame, text="Add. params: ").grid(row=row, column=0, sticky="NE")
        self.params = StringVar(master)
        self.entry_params = Entry(self.frame, textvariable = self.params)
        self.entry_params.grid(row=row, column=1, sticky="NEW")

        # closed-world predicates
        row += 1
        Label(self.frame, text="CW preds: ").grid(row=row, column=0, sticky="NE")
        self.cwPreds = StringVar(master)
        self.cwPreds.set(self.settings.get("cwPreds", ""))
        self.entry_cw = Entry(self.frame, textvariable = self.cwPreds)
        self.entry_cw.grid(row=row, column=1, sticky="NEW")

        # all preds open-world
        option_container = Frame(self.frame)
        option_container.grid(row=row, column=1, sticky="NES")
        row += 1
        self.closed_world = IntVar()
        self.closed_world.trace('w', self.onChangeClosedWorld)
        self.cb_closed_world = Checkbutton(option_container, text="Apply CW assumption to all but the query preds", variable=self.closed_world)
        self.cb_closed_world.grid(row=row, column=1, sticky=W)
        self.closed_world.set(self.settings.get("closedWorld", False))
        
        # Multiprocessing 
        self.use_multiCPU = IntVar()
        self.cb_use_multiCPU = Checkbutton(option_container, text="Use all CPUs", variable=self.use_multiCPU)
        self.cb_use_multiCPU.grid(row=row, column=2, sticky=W)
        self.use_multiCPU.set(self.settings.get("useMultiCPU", False))

        # output filename
        row += 1
        Label(self.frame, text="Output: ").grid(row=row, column=0, sticky="NE")
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        frame.columnconfigure(0, weight=1)
        # - filename
        self.output_filename = StringVar(master)
        self.output_filename.set(self.settings.get("output_filename", ""))
        self.entry_output_filename = Entry(frame, textvariable = self.output_filename)
        self.entry_output_filename.grid(row=0, column=0, sticky="NEW")
        # - save option
        self.save_results = IntVar()
        self.cb_save_results = Checkbutton(frame, text="save", variable=self.save_results)
        self.cb_save_results.grid(row=0, column=1, sticky=W)

        self.save_results.set(self.settings.get("saveResults", 0))
        # start button
        row += 1
        start_button = Button(self.frame, text=">> Start Inference <<", command=self.start)
        start_button.grid(row=row, column=1, sticky="NEW")

        self.initialized = True
        self.onChangeEngine()
        self.onChangeClosedWorld()
        self.setGeometry()

    def setGeometry(self):
        g = self.settings.get("geometry")
        if g is None: return
        # this is a hack: since geometry apparently does not work as expected
        # (at least under Ubuntu: the main window is not put at the same position
        # where it has been before), do this correction of coordinates.
        re_pattern = r'([\-0-9]+)x([\-0-9]+)\+([\-0-9]+)\+([\-0-9]+)'
        (w_old, h_old, x_old, y_old) = map(int, re.search(re_pattern, g).groups())
        self.master.geometry(g)
        new_g = self.master.winfo_geometry()
        (w_new, h_new, x_new, y_new) = map(int, re.search(re_pattern, new_g).groups())
        (w_diff, h_diff, x_diff, y_diff) = (w_old-w_new, h_old-h_new, x_old-x_new, y_old-y_new)
        (w_new, h_new, x_new, y_new) = (w_old, h_old, x_new-x_diff, y_new-y_diff)
        self.master.geometry('%dx%d+%d+%d' % (w_new, h_new, x_new, y_new))
         

    def changedMLN(self, name):
        self.mln_filename = name
        self.setOutputFilename()

    def changedDB(self, name):
        self.db_filename = name
        self.setOutputFilename()
        # restore stored query (if any)
        query = self.settings["queryByDB"].get(name)
        if query is None: # try file
            query_file = "%s.query" % name
            if os.path.exists(query_file) and "query" in dir(self):
                f = file(query_file, "r")
                query = f.read()
                f.close()
        if not query is None and hasattr(self, "query"):
            self.query.set(query)
        # select EMLN
        emln = self.settings["emlnByDB"].get(name)
        if not emln is None:
            self.selected_emln.set(emln)
            
    def onChangeUseMultiCPU(self, *args):
        pass

    def onChangeUseEMLN(self, *args):
        if self.use_emln.get() == 0:
            self.selected_emln.grid_forget()
        else:
            self.selected_emln.grid(row=self.selected_mln.row+1, column=0, sticky="NWES")

    def onChangeLogic(self, name = None, index = None, mode = None):
        pass
    
    def onChangeClosedWorld(self, name=None, index=None, mode=None):
        if self.closed_world.get():
            self.entry_cw.configure(state=DISABLED)
        else:
            self.entry_cw.configure(state=NORMAL)
        
    
    def onChangeGrammar(self, name=None, index=None, mode=None):
        grammar = eval(self.selected_grammar.get())(None)
        self.selected_mln.editor.grammar = grammar        

    def onChangeEngine(self, name = None, index = None, mode = None):
        # enable/disable controls
        engineName = self.selected_engine.get()
        if engineName in ("internal", "PRACMLNs"):
            self.numEngine = 1
            methods = self.inference.pymlns_methods
            #self.entry_output_filename.configure(state=NORMAL)
            self.cb_save_results.configure(state=NORMAL)
        elif engineName == "J-MLNs":
            self.numEngine = 2
            methods = self.inference.jmlns_methods.keys()
            #self.entry_output_filename.configure(state=NORMAL)
            self.cb_closed_world.configure(state=DISABLED)
            self.cb_save_results.configure(state=NORMAL)
        else:
            self.numEngine = 0
            methods = self.inference.alchemy_methods.keys()
            #self.entry_output_filename.configure(state=NORMAL)
            self.cb_closed_world.configure(state=NORMAL)
            self.cb_save_results.configure(state=DISABLED)

        # change additional parameters
        self.params.set(self.settings.get("params%d" % int(self.numEngine), ""))

        # change selected inference methods
        preferredMethod = self.settings.get("method%d" % int(self.numEngine), methods[0])
        if preferredMethod not in methods: preferredMethod = methods[0]
        self.selected_method.set(preferredMethod)

        # change list control
        if "list_methods" in dir(self): self.list_methods.grid_forget()
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methods))
        self.list_methods.grid(row=self.list_methods_row, column=1, sticky="NWE")

    def setOutputFilename(self):
        if not self.initialized or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        fn = config.query_output_filename(self.mln_filename, self.db_filename)
        self.output_filename.set(fn)

    def start(self, saveGeometry = True):
        mln = self.selected_mln.get()
        emln = self.selected_emln.get()
        db = self.selected_db.get()
        qf = self.selected_qf.get()
        mln_text = self.selected_mln.get_text()
        db_text = self.selected_db.get_text()
        qf_text = self.selected_qf.get_text()
        output = self.output_filename.get()
        method = self.selected_method.get()
        params = self.params.get()
        # update settings
        self.settings["mln"] = mln
        self.settings["mln_rename"] = self.selected_mln.rename_on_edit.get()
        self.settings["db"] = db
        self.settings["db_rename"] = self.selected_db.rename_on_edit.get()
        self.settings["method%d" % int(self.numEngine)] = method
        self.settings["params%d" % int(self.numEngine)] = params
        self.settings["query"] = self.query.get()
        self.settings["queryByDB"][db] = self.settings["query"]
        self.settings["emlnByDB"][db] = emln
        self.settings["engine"] = self.selected_engine.get()
        self.settings["qf"] = qf
        self.settings["output_filename"] = output
        self.settings["closedWorld"] = self.closed_world.get()
        self.settings["cwPreds"] = self.cwPreds.get()
        self.settings["convertAlchemy"] = self.convert_to_alchemy.get()
        self.settings["useEMLN"] = self.use_emln.get()
        self.settings["maxSteps"] = self.maxSteps.get()
        self.settings["numChains"] = self.numChains.get()
        self.settings['logic'] = self.selected_logic.get()
        self.settings['grammar'] = self.selected_grammar.get()
        self.settings['useMultiCPU'] = self.use_multiCPU.get()
        
        
        if "params" in self.settings: del self.settings["params"]
        if saveGeometry:
            self.settings["geometry"] = self.master.winfo_geometry()
        self.settings["saveResults"] = self.save_results.get()
        # write query to file
        write_query_file = False
        if write_query_file:
            query_file = "%s.query" % db
            f = file(query_file, "w")
            f.write(self.settings["query"])
            f.close()
        # write settings
        pickle.dump(self.settings, file(configname, "w+"))
        
        # some information
        print "\n--- query ---\n%s" % self.settings["query"]        
        print "\n--- evidence (%s) ---\n%s" % (db, db_text.strip())
        # MLN input files
        input_files = [mln]
        if settings["useEMLN"] == 1 and emln != "": # using extended model
            input_files.append(emln)
        # hide main window
        self.master.withdraw()
        
        # runinference
        try:
            self.inference.run(input_files, db, method, self.settings["query"], params=params, **self.settings)
        except:
            cls, e, tb = sys.exc_info()
            sys.stderr.write("Error: %s\n" % str(e))
            traceback.print_tb(tb)
        # restore main window
        self.master.deiconify()
        self.setGeometry()
        # reload the files (in case they changed)
        self.selected_mln.reloadFile()
        self.selected_db.reloadFile()

        sys.stdout.flush()

# -- main app --

if __name__ == '__main__':
    # read command-line options
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-i", "--mln", dest="mln", help="the MLN model file to use")
    parser.add_option("-q", "--queries", dest="query", help="queries (comma-separated)")
    parser.add_option("-e", "--evidence", dest="db", help="the evidence database file")
    parser.add_option("-r", "--results-file", dest="output_filename", help="the results file to save")
    parser.add_option("--run", action="store_true", dest="run", default=False, help="run with last settings (without showing GUI)")
    parser.add_option("--noPMW", action="store_true", dest="noPMW", default=False, help="do not use Python mega widgets even if available")
    (options, args) = parser.parse_args()

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

    # update settings with command-line information
    settings.update(dict(filter(lambda x: x[1] is not None, options.__dict__.iteritems())))
    if len(args) > 1:
        settings["params"] = (settings.get("params", "") + " ".join(args)).strip()

    # create gui
    if options.noPMW:
        widgets.havePMW = False
    root = Tk()
    app = MLNQueryGUI(root, ".", settings)
    if options.run:
        app.start(saveGeometry=False)
    else:
        root.mainloop()

