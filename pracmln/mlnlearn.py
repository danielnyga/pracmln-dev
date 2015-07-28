#!/usr/bin/python
# -*- coding: utf-8 -*-

# MLN Parameter Learning Tool
#
# (C) 2012-2015 by Daniel Nyga
#     2006-2007 by Dominik Jain
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
import re
import pickle
import traceback
from utils.widgets import *
import subprocess
import shlex
import tkMessageBox
from fnmatch import fnmatch
from pprint import pprint
from mln.methods import LearningMethods
import cProfile
from cProfile import Profile
import logging
from mln import MLN
from logic import StandardGrammar, PRACGrammar
from logic import FirstOrderLogic, FuzzyLogic

# --- generic learning interface ---

class MLNLearn:
    
    def __init__(self):
        self.pymlns_methods = LearningMethods.getNames()
    
    def run(self, **kwargs):
        '''
            required arguments:
                training databases(s): either one of
                    "dbs": list of database filenames (or MLN.Database objects for PyMLNs)
                    "db": database filename
                    "pattern": file mask pattern from which to generate the list of databases
                "mln": an MLN filename (or MLN.MLN object for PyMLNs)
                "method": the learning method name
                "output_filename": the output filename
            
            optional arguments:
                "engine": either "PRACMLNs" (default) or one of the Alchemy versions defined in the config
                "initialWts": (true/false)
                "usePrior": (true/false); default: False
                "priorStdDev": (float) standard deviation of prior when usePrior=True
                "addUnitClauses": (true/false) whether to add unit clauses (Alchemy only); default: False
                "params": (string) additional parameters to pass to the learner; for Alchemy: command-line parameters; for PyMLNs: either dictionary string (e.g. "foo=bar, baz=2") or a dictionary object
                ...
        '''
        defaults = {
            "engine": "PRACMLNs",
            "usePrior": False,
            "priorStdDev": 10.0,
            "addUnitClauses": False,
            "params": ""
        }
        self.settings = defaults
        self.settings.update(kwargs)
        
        
        # determine training databases(s)
        if "dbs" in self.settings:
            dbs = self.settings["dbs"]
        elif "db" in self.settings and self.settings["db"] != "":
            dbs = [self.settings["db"]]
        elif "pattern" in self.settings and self.settings["pattern"] != "":
            dbs = []
            pattern = settings["pattern"]
            dir, mask = os.path.split(os.path.abspath(pattern))
            for fname in os.listdir(dir):
                if fnmatch(fname, mask):
                    dbs.append(os.path.join(dir, fname))
            if len(dbs) == 0:
                raise Exception("The pattern '%s' matches no files" % pattern)
            print "training databases:", ",".join(dbs)
        else:
            raise Exception("No training data given; A training database must be selected or a pattern must be specified")        
        
        # check if other required arguments are set
        missingSettings = set(["mln", "method", "output_filename"]).difference(set(self.settings.keys()))
        if len(missingSettings) > 0:
            raise Exception("Some required settings are missing: %s" % str(missingSettings))

        params = self.settings["params"]
        method = self.settings["method"]
        discriminative = "discriminative" in method
        
        #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  
        #  PRACMLN internal engine
        #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
        
        if self.settings["engine"] in ("PRACMLNs", "internal"): # PyMLNs internal engine
        
            # arguments
            args = {}
            if type(params) == str:
                params = eval("dict(%s)" % params)
            
            elif type(params) != dict:
                raise("Argument 'params' must be string or a dictionary")
            
            # multiprocessing settings
            args['useMultiCPU'] = self.settings.get('useMultiCPU', False)
            args.update(params) # add additional parameters
            
            # settings for discriminative learning
            if discriminative:
                if settings.get('discrPredicates', MLNLearnGUI.USE_QUERY_PREDS) == MLNLearnGUI.USE_QUERY_PREDS:
                    args["queryPreds"] = map(str.strip, self.settings["queryPreds"].split(","))
                else:
                    args['evidencePreds'] = map(str.strip, self.settings['evidencePreds'].split(','))

            # gaussian prior settings            
            if self.settings["usePrior"]:
                args["gaussianPriorSigma"] = float(self.settings["priorStdDev"])
                args["gaussianPriorMean"] = float(self.settings["priorMean"])

            # incremental learning
            if self.settings["incremental"]:
                args["incremental"] = True 

            # shuffle databases
            if self.settings["shuffle"]:
                args["shuffle"] = True 
            
            # learn weights
            if type(self.settings["mln"]) == str:
                mln = MLN(mlnfile=self.settings["mln"], logic=self.settings['logic'], grammar=self.settings['grammar'])
                
            elif type(self.settings["mln"] == mln.MLN):
                mln = self.settings["mln"]
            else:
                raise Exception("Argument 'mln' must be either string or MLN object")
            
            print args
            
            # set the debug level
            logging.getLogger().setLevel(eval('logging.%s' % args.get('debug', 'WARNING').upper()))
            
            if args.get('profile', False):
                prof = Profile()
                try:
                    print 'Profiling ON...'
                    cmd = 'mln.learnWeights(dbs, method=LearningMethods.byName(method), **args)'
                    prof = prof.runctx(cmd, globals(), locals())
                except SystemExit:
                    print 'Cancelled...'
                finally:
                    print 'Profiler Statistics:'
                    prof.print_stats(-1)
            else:
                learnedMLN = mln.learnWeights(dbs, method=LearningMethods.byName(method), **args)
            
            # determine output filename
            fname = self.settings["output_filename"]
            learnedMLN.write(file(fname, "w"))
            print "\nWROTE %s\n\n" % fname
            if args.get('output', False):
                learnedMLN.write(sys.stdout, color=True)
            
            
# --- gui class ---

class MLNLearnGUI:

    USE_QUERY_PREDS = 0
    USE_EVIDENCE_PREDS = 1

    def file_pick(self, label, mask, row, default, change_hook = None):
        # create label
        Label(self.frame, text=label).grid(row=row, column=0, sticky="E")
        # read filenames
        files = []
        for filename in os.listdir(self.dir):
            if fnmatch(filename, mask):
                files.append(filename)
        files.sort()
        if len(files) == 0: files.append("(no %s files found)" % mask)
        # create list
        stringvar = StringVar(self.master)
        if default in files:
            stringvar.set(default) # default value
        list = apply(OptionMenu, (self.frame, stringvar) + tuple(files))
        list.grid(row=row, column=1, sticky="EW")
        #list.configure(width=self.stdWidth)
        if change_hook != None:
            stringvar.trace("w", change_hook)
        return stringvar

    def __init__(self, master, dir, settings):
        self.master = master
        self.master.title("MLN Parameter Learning Tool")
        self.dir = dir
        self.settings = settings
        self.learner = MLNLearn()

        self.frame = Frame(master)
        self.frame.pack(fill=BOTH, expand=1)
        self.frame.columnconfigure(1, weight=1)

        # engine selection
        row = 0        
        Label(self.frame, text="Engine: ").grid(row=row, column=0, sticky="E")
        engines = ["PRACMLNs"]
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

        row += 1
        Label(self.frame, text="MLN: ").grid(row=row, column=0, sticky="NE")
        self.selected_mln = FilePickEdit(self.frame, config.learnwts_mln_filemask, self.settings.get("mln"), 20, self.changedMLN, font=config.fixed_width_font)
        self.selected_mln.grid(row=row,column=1, sticky="NEWS")
        self.frame.rowconfigure(row, weight=1)
        #self.selected_mln = self.file_pick("MLN: ", "*.mln", row, self.settings.get("mln"), self.changedMLN)

        # method selection
        row += 1
        self.list_methods_row = row
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        ## create list in onChangeEngine
        
        # additional parametrisation
        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        # option: use prior
        self.use_prior = IntVar()
        self.cb_use_prior = Checkbutton(frame, text="use prior with mean of ", variable=self.use_prior)
        self.cb_use_prior.pack(side=LEFT)
        self.use_prior.set(self.settings.get("usePrior", 0))
        # set prior 
        self.priorMean = StringVar(master)        
        self.priorMean.set(self.settings.get("priorMean", "0"))       
        Entry(frame, textvariable = self.priorMean, width=5).pack(side=LEFT)
        Label(frame, text=" and std dev of ").pack(side=LEFT)
        # std. dev.
        self.priorStdDev = StringVar(master)
        self.priorStdDev.set(self.settings.get("priorStdDev", "2"))
        Entry(frame, textvariable = self.priorStdDev, width=5).pack(side=LEFT)
        # use initial weights in MLN 
        self.use_initial_weights = IntVar()
        self.cb_use_initial_weights = Checkbutton(frame, text="use initial weights", variable=self.use_initial_weights)
        self.cb_use_initial_weights.pack(side=LEFT)
        self.use_initial_weights.set(self.settings.get("use_initial_weights", "0"))
        # use incremental learning
        self.incremental = IntVar()
        self.cb_incremental = Checkbutton(frame, text=" learn incrementally ", variable=self.incremental, command=self.check_incremental)
        self.cb_incremental.pack(side=LEFT)
        self.incremental.set(self.settings.get("incremental", "0"))
        # shuffle databases
        self.shuffle = IntVar()
        self.cb_shuffle = Checkbutton(frame, text="shuffle databases", variable=self.shuffle, state='disabled')
        self.cb_shuffle.pack(side=LEFT)
        self.shuffle.set(self.settings.get("shuffle", "0"))
        # add unit clauses
        self.add_unit_clauses = IntVar()
        self.cb_add_unit_clauses = Checkbutton(frame, text="add unit clauses", variable=self.add_unit_clauses)
        self.cb_add_unit_clauses.pack(side=LEFT)
        self.add_unit_clauses.set(self.settings.get("addUnitClauses", 0))
        
        # discriminative learning settings
        row += 1
        self.discrPredicates = IntVar()
        
        frame = Frame(self.frame)        
        frame.grid(row=row, column=1, sticky="NEWS")
        self.rbQueryPreds = Radiobutton(frame, text="Query preds:", variable=self.discrPredicates, value=MLNLearnGUI.USE_QUERY_PREDS)
        self.rbQueryPreds.grid(row=0, column=0, sticky="NE")
                
        self.queryPreds = StringVar(master)
        self.queryPreds.set(self.settings.get("queryPreds", ""))
        frame.columnconfigure(1, weight=1)
        self.entry_nePreds = Entry(frame, textvariable = self.queryPreds)
        self.entry_nePreds.grid(row=0, column=1, sticky="NEW")        

        self.rbEvidencePreds = Radiobutton(frame, text='Evidence preds', variable=self.discrPredicates, value=MLNLearnGUI.USE_EVIDENCE_PREDS)
        self.rbEvidencePreds.grid(row=0, column=2, sticky='NEWS')
        
        self.evidencePreds = StringVar(master)
        self.evidencePreds.set(self.settings.get("evidencePreds", ""))
        self.entryEvidencePreds = Entry(frame, textvariable=self.evidencePreds)
        self.entryEvidencePreds.grid(row=0, column=3, sticky='NEWS')

        self.discrPredicates.set(self.settings.get('discrPredicates', MLNLearnGUI.USE_QUERY_PREDS))

        # evidence database selection
        row += 1
        Label(self.frame, text="Training data: ").grid(row=row, column=0, sticky="NE")
        self.selected_db = FilePickEdit(self.frame, config.learnwts_db_filemask, self.settings.get("db"), 15, self.changedDB, font=config.fixed_width_font, allowNone=True)
        self.selected_db.grid(row=row, column=1, sticky="NEWS")
        self.frame.rowconfigure(row, weight=1)

        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        col = 0
        Label(frame, text="OR Pattern:").grid(row=0, column=col, sticky="W")
        # - pattern entry
        col += 1
        frame.columnconfigure(col, weight=1)
        self.pattern = var = StringVar(master)
        var.set(self.settings.get("pattern", ""))
        self.entry_pattern = Entry(frame, textvariable = var)
        self.entry_pattern.grid(row=0, column=col, sticky="NEW")

        # add. parameters
        row += 1
        Label(self.frame, text="Params: ").grid(row=row, column=0, sticky="E")
        self.params = StringVar(master)
        self.params.set(self.settings.get("params", ""))
        Entry(self.frame, textvariable = self.params).grid(row=row, column=1, sticky="NEW")
        
        # Multiprocessing 
        self.use_multiCPU = IntVar()
        self.cb_use_multiCPU = Checkbutton(self.frame, text="Use all CPUs", variable=self.use_multiCPU)
        self.cb_use_multiCPU.grid(row=row, column=1, sticky=E)
        self.use_multiCPU.set(self.settings.get("useMultiCPU", False))

        row += 1
        Label(self.frame, text="Output filename: ").grid(row=row, column=0, sticky="E")
        self.output_filename = StringVar(master)
        self.output_filename.set(self.settings.get("output_filename", ""))
        Entry(self.frame, textvariable = self.output_filename).grid(row=row, column=1, sticky="EW")

        row += 1
        learn_button = Button(self.frame, text=" >> Learn << ", command=self.learn)
        learn_button.grid(row=row, column=1, sticky="EW")

        self.onChangeEngine()
        self.onChangeMethod()
        self.setGeometry()

    def setGeometry(self):
        g = self.settings.get("geometry")
        if g is None: return
        self.master.geometry(g)

    def onChangeEngine(self, name = None, index = None, mode = None):
        # enable/disable controls
        if self.selected_engine.get() == "PRACMLNs":
            state = DISABLED
            self.internalMode = True
            methods = sorted(self.learner.pymlns_methods)
        else:
            state = NORMAL
            self.internalMode = False
            methods = sorted(self.learner.alchemy_methods.keys())
        self.cb_add_unit_clauses.configure(state=state)  

        # change additional parameters
        self.params.set(self.settings.get("params%d" % int(self.internalMode), ""))

        # change supported inference methods
        selected_method = self.settings.get("method%d" % int(self.internalMode))
        if selected_method not in methods:
#             if selected_method == "discriminative learning": selected_method = "[discriminative] sampling-based log-likelihood via rescaled conjugate gradient"
            selected_method = LearningMethods.getName("BPLL_CG")
            
        self.selected_method.set(selected_method) # default value
        if "list_methods" in dir(self): self.list_methods.grid_forget()
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methods))
        self.list_methods.grid(row=self.list_methods_row, column=1, sticky="NWE")
        self.selected_method.trace("w", self.changedMethod)

    def check_incremental(self):

        if self.incremental.get()==1:
            self.cb_shuffle.configure(state="normal")  
        else:
            self.cb_shuffle.configure(state="disabled")
            self.cb_shuffle.deselect()
                

    def isFile(self, f):
        return os.path.exists(os.path.join(self.dir, f))

    def setOutputFilename(self):
        if not hasattr(self, "output_filename") or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        mln = self.mln_filename
        db = self.db_filename
        if "" in (mln, db): return
        if self.internalMode:
            engine = "py"
            method = LearningMethods.byName(self.selected_method.get())
            method = LearningMethods.getShortName(method).lower()
        else:
            engine = "alch"
            method = self.learner.alchemy_methods[self.selected_method.get()][2]
        filename = config.learnwts_output_filename(mln, engine, method, db)
        self.output_filename.set(filename)
        

    def changedMLN(self, name):
        self.mln_filename = name
        self.setOutputFilename()

    def changedDB(self, name):
        self.db_filename = name
        self.setOutputFilename()

    def onChangeLogic(self, name = None, index = None, mode = None):
        pass
    
    def onChangeGrammar(self, name=None, index=None, mode=None):
        grammar = eval(self.selected_grammar.get())(None)
        self.selected_mln.editor.grammar = grammar        

    def onChangeMethod(self):
        method = self.selected_method.get()
        state = NORMAL if "[discriminative]" in method else DISABLED
        self.entry_nePreds.configure(state=state)
        self.entryEvidencePreds.configure(state=state)
        self.rbQueryPreds.configure(state=state)        
        self.rbEvidencePreds.configure(state=state)

    def changedMethod(self, name, index, mode):
        self.onChangeMethod()
        self.setOutputFilename()

    def learn(self, saveGeometry=True):
        try:
            # update settings
            mln = self.selected_mln.get()
            db = self.selected_db.get()
            if mln == "":
                raise Exception("No MLN was selected")
            method = self.selected_method.get()
            params = self.params.get()
            self.settings["mln"] = mln
            self.settings["db"] = db
            self.settings["output_filename"] = self.output_filename.get()
            self.settings["params%d" % int(self.internalMode)] = params
            self.settings["engine"] = self.selected_engine.get()
            self.settings["method%d" % int(self.internalMode)] = method
            self.settings["pattern"] = self.entry_pattern.get()
            self.settings["usePrior"] = int(self.use_prior.get())
            # for incremental learning
            self.settings["priorMean"] = self.priorMean.get()
            self.settings["priorStdDev"] = self.priorStdDev.get()
            self.settings["incremental"] = int(self.incremental.get())
            self.settings["shuffle"] = int(self.shuffle.get())
            self.settings["use_initial_weights"] = int(self.use_initial_weights.get())

            self.settings["queryPreds"] = self.queryPreds.get()
            self.settings["evidencePreds"] = self.evidencePreds.get()
            self.settings["discrPredicates"] = self.discrPredicates.get()
            self.settings["addUnitClauses"] = int(self.add_unit_clauses.get())
            self.settings['logic'] = self.selected_logic.get()
            self.settings['grammar'] = self.selected_grammar.get()
            self.settings['useMultiCPU'] = self.use_multiCPU.get()
            
            if saveGeometry:
                self.settings["geometry"] = self.master.winfo_geometry()
            pickle.dump(self.settings, file("learnweights.config.dat", "w+"))

            # hide gui
            self.master.withdraw()
            
            # invoke learner
            self.learner.run(params=params, method=method, **self.settings)
            
            if config.learnwts_edit_outfile_when_done:
                params = [config.editor, self.settings["output_filename"]]
                print "starting editor: %s" % subprocess.list2cmdline(params)
                subprocess.Popen(params, shell=False)
        except:
            cls, e, tb = sys.exc_info()
            logging.exception("%s: %s\n" % (str(e.__class__.__name__), str(e)))
#             traceback.print_tb(tb)
#             raise
        finally:
            # restore gui
            self.master.deiconify()
            self.setGeometry()

            sys.stdout.flush()

# -- main app --

if __name__ == '__main__':
    # read command-line options
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("--run", action="store_true", dest="run", default=False, help="run last configuration without showing gui")
    parser.add_option("-i", "--mln-filename", dest="mln_filename", help="input MLN filename", metavar="FILE", type="string")
    parser.add_option("-t", "--db-filename", dest="db", help="training database filename", metavar="FILE", type="string")
    parser.add_option("-o", "--output-file", dest="output_filename", help="output MLN filename", metavar="FILE", type="string")
    (options, args) = parser.parse_args()

    # read previously saved settings
    settings = {}
    if os.path.exists("learnweights.config.dat"):
        try:
            settings = pickle.loads("\n".join(map(lambda x: x.strip("\r\n"), file("learnweights.config.dat", "r").readlines())))
        except:
            pass
    # update settings with command-line options
    settings.update(dict(filter(lambda x: x[1] is not None, options.__dict__.iteritems())))

    # run learning task/GUI
    root = Tk()
    app = MLNLearnGUI(root, ".", settings)
    #print "options:", options
    if options.run:
        app.learn(saveGeometry=False)
    else:
        root.mainloop()

