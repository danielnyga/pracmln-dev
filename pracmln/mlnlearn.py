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
from pracmln.utils import config
from pracmln.mln.util import ifNone, out
from tkMessageBox import showerror, askyesno
from tkFileDialog import askdirectory
from pracmln.utils.config import learn_config_pattern, PRACMLNConfig
from pracmln import praclog

logger = praclog.logger(__name__)

# --- generic learning interface ---

class MLNLearn:
    
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


    def __init__(self, master, gconf, directory=None):
        self.master = master
        self.master.title("PRACMLN Learning Tool")
        
        self.initialized = False
        
        self.gconf = gconf
        
        self.learner = MLNLearn()

        self.frame = Frame(master)
        self.frame.pack(fill=BOTH, expand=1)
        self.frame.columnconfigure(1, weight=1)

        row = 0        

        # grammar selection
        Label(self.frame, text='Grammar: ').grid(row=row, column=0, sticky='E')
        grammars = ['StandardGrammar', 'PRACGrammar']
        self.selected_grammar = StringVar(master)
        self.selected_grammar.trace('w', self.onChangeGrammar)
        l = apply(OptionMenu, (self.frame, self.selected_grammar) + tuple(grammars))
        l.grid(row=row, column=1, sticky='NWE')
        
        # logic selection
        row += 1
        Label(self.frame, text='Logic: ').grid(row=row, column=0, sticky='E')
        logics = ['FirstOrderLogic', 'FuzzyLogic']
        self.selected_logic = StringVar(master)
        self.selected_logic.trace('w', self.onChangeLogic)
        l = apply(OptionMenu, (self.frame, self.selected_logic) + tuple(logics))
        l.grid(row=row, column=1, sticky='NWE')
        
        # folder selection
        row += 1
        self.dir = StringVar(master)
        Label(self.frame, text='Directory:').grid(row=row, column=0, sticky='NES')
        self.text_dir = Entry(self.frame, textvariable=self.dir)
        self.text_dir.grid(row=row, column=1, sticky="NEWS")
        self.text_dir.bind('<FocusOut>', self.update_dir)
        self.text_dir.bind('<Return>', self.update_dir)
        self.btn_dir = Button(self.frame, text='Browse...', command=self.select_dir)
        self.btn_dir.grid(row=row, column=1, sticky="NES")
        
        # mln selection
        row += 1
        Label(self.frame, text="MLN: ").grid(row=row, column=0, sticky='NE')
        self.selected_mln = FilePickEdit(self.frame, config.learnwts_mln_filemask, '', 22, 
                                         self.select_mln, rename_on_edit='', 
                                         font=config.fixed_width_font, coloring=True)
        self.selected_mln.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # method selection
        row += 1
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        methods = sorted(LearningMethods.getNames())
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methods))
        self.list_methods.grid(row=row, column=1, sticky="NWE")
        self.selected_method.trace("w", self.changedMethod)
        
        # additional parametrization
        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        
        # use prior
        self.use_prior = IntVar()
        self.cb_use_prior = Checkbutton(frame, text="use prior with mean of ", variable=self.use_prior)
        self.cb_use_prior.pack(side=LEFT)
        
        # set prior 
        self.priorMean = StringVar(master)        
        Entry(frame, textvariable = self.priorMean, width=5).pack(side=LEFT)
        Label(frame, text=" and std dev of ").pack(side=LEFT)
        
        # std. dev.
        self.priorStdDev = StringVar(master)
        Entry(frame, textvariable = self.priorStdDev, width=5).pack(side=LEFT)
        
        # use initial weights in MLN 
        self.use_initial_weights = IntVar()
        self.cb_use_initial_weights = Checkbutton(frame, text="use initial weights", variable=self.use_initial_weights)
        self.cb_use_initial_weights.pack(side=LEFT)
        
        # use incremental learning
        self.incremental = IntVar()
        self.cb_incremental = Checkbutton(frame, text=" learn incrementally ", variable=self.incremental, command=self.check_incremental)
        self.cb_incremental.pack(side=LEFT)
        
        # shuffle databases
        self.shuffle = IntVar()
        self.cb_shuffle = Checkbutton(frame, text="shuffle databases", variable=self.shuffle, state='disabled')
        self.cb_shuffle.pack(side=LEFT)
        
        # discriminative learning settings
        row += 1
        self.discrPredicates = IntVar()
        
        frame = Frame(self.frame)        
        frame.grid(row=row, column=1, sticky="NEWS")
        self.rbQueryPreds = Radiobutton(frame, text="Query preds:", variable=self.discrPredicates, value=MLNLearnGUI.USE_QUERY_PREDS)
        self.rbQueryPreds.grid(row=0, column=0, sticky="NE")
                
        self.queryPreds = StringVar(master)
        frame.columnconfigure(1, weight=1)
        self.entry_nePreds = Entry(frame, textvariable = self.queryPreds)
        self.entry_nePreds.grid(row=0, column=1, sticky="NEW")        

        self.rbEvidencePreds = Radiobutton(frame, text='Evidence preds', variable=self.discrPredicates, value=MLNLearnGUI.USE_EVIDENCE_PREDS)
        self.rbEvidencePreds.grid(row=0, column=2, sticky='NEWS')
        
        self.evidencePreds = StringVar(master)
        self.entryEvidencePreds = Entry(frame, textvariable=self.evidencePreds)
        self.entryEvidencePreds.grid(row=0, column=3, sticky='NEWS')


        # evidence database selection
        row += 1
        Label(self.frame, text="Training data: ").grid(row=row, column=0, sticky="NE")
        self.selected_db = FilePickEdit(self.frame, config.learnwts_db_filemask, '', 15, self.changedDB, font=config.fixed_width_font
                                        )
        self.selected_db.grid(row=row, column=1, sticky="NEWS")
        self.frame.rowconfigure(row, weight=1)

        # file patterns
        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        col = 0
        Label(frame, text="OR file pattern:").grid(row=0, column=col, sticky="W")
        # - pattern entry
        col += 1
        frame.columnconfigure(col, weight=1)
        self.pattern = StringVar(master)
        self.entry_pattern = Entry(frame, textvariable=self.pattern)
        self.entry_pattern.grid(row=0, column=col, sticky="NEW")

        # add. parameters
        row += 1
        Label(self.frame, text="Add. Params: ").grid(row=row, column=0, sticky="E")
        self.params = StringVar(master)
        Entry(self.frame, textvariable = self.params).grid(row=row, column=1, sticky="NEW")
        
        # options
        row += 1
        option_container = Frame(self.frame)
        option_container.grid(row=row, column=1, sticky="NEWS")

        # multicore
        self.use_multiCPU = IntVar()
        self.cb_multicore = Checkbutton(option_container, text="Use all CPUs", variable=self.use_multiCPU)
        self.cb_multicore.grid(row=0, column=1, sticky=E)
        
        # profiling
        self.profile = IntVar()
        self.cb_profile = Checkbutton(option_container, text='Use Profiler', variable=self.profile)
        self.cb_profile.grid(row=0, column=3, sticky=W)
        
        # verbose
        self.verbose = IntVar()
        self.cb_verbose = Checkbutton(option_container, text='verbose', variable=self.verbose)
        self.cb_verbose.grid(row=0, column=4, sticky=W)

        row += 1
        Label(self.frame, text="Output filename: ").grid(row=row, column=0, sticky="E")
        self.output_filename = StringVar(master)
        Entry(self.frame, textvariable = self.output_filename).grid(row=row, column=1, sticky="EW")

        row += 1
        learn_button = Button(self.frame, text=" >> Learn << ", command=self.learn)
        learn_button.grid(row=row, column=1, sticky="EW")

        self.set_dir(ifNone(directory, ifNone(gconf['prev_learnwts_path'], os.getcwd())))
        if gconf['prev_learnwts_mln':self.dir.get()] is not None:
            self.selected_mln.set(gconf['prev_learnwts_mln':self.dir.get()])
        
        self.set_window_loc(gconf['window_loc_learn'])
        
        self.initialized = True


    def set_window_loc(self, location):
        g = location
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
        

    def update_dir(self, e):
        d = self.dir.get()
        if not os.path.exists(d):
            showerror('Directory not found', 'No such directory: "%s"' % d)
            self.set_dir(self.selected_mln.directory)
        else:
            self.set_dir(d)
            
            
    def set_dir(self, dirpath):
        dirpath = os.path.abspath(dirpath)
        self.selected_mln.setDirectory(dirpath)
        self.selected_db.setDirectory(dirpath)
        self.dir.set(dirpath)
        
        
    def select_dir(self):
        dirname = askdirectory()
        if dirname: self.set_dir(dirname)

    
    def select_mln(self, mlnname):
        confname = os.path.join(self.dir.get(), learn_config_pattern % mlnname)
        if not self.initialized or os.path.exists(confname) and askyesno('PRACMLN', 'A configuration file was found for the selected MLN.\nDo want to load the configuration?'):
            self.set_config(PRACMLNConfig(confname))
        self.mln_filename = mlnname
        self.setOutputFilename()
            
            
    def check_incremental(self):
        if self.incremental.get()==1:
            self.cb_shuffle.configure(state="normal")  
        else:
            self.cb_shuffle.configure(state="disabled")
            self.cb_shuffle.deselect()
                

    def isFile(self, f):
        return os.path.exists(os.path.join(self.dir.get(), f))


    def setOutputFilename(self):
        if not hasattr(self, "output_filename") or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        mln = self.mln_filename
        db = self.db_filename
        if "" in (mln, db): return
        if self.selected_method.get():
            method = LearningMethods.byName(self.selected_method.get())
            method = LearningMethods.getShortName(method).lower()
            filename = config.learnwts_output_filename(mln, method, db)
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
        if self.selected_grammar.get():
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


    def set_config(self, conf):
        self.config = conf
#         self.selected_db.set(ifNone(self.config["db"], ''))
        self.selected_grammar.set(ifNone(conf['grammar'], 'PRACGrammar'))
        self.selected_logic.set(ifNone(conf['logic'], 'FirstOrderLogic'))
        self.output_filename.set(ifNone(self.config["output_filename"], ''))
        self.params.set(ifNone(self.config["params"], ''))
        self.selected_method.set(ifNone(self.config["method"], ''))
        self.pattern.set(ifNone(self.config["pattern"], ''))
        self.use_prior.set(ifNone(self.config["use_prior"], False))
        self.priorMean.set(ifNone(self.config["prior_mean"], 0))
        self.priorStdDev.set(ifNone(self.config["prior_stdev"], 0))
        self.incremental.set(ifNone(self.config["incremental"], False))
        self.shuffle.set(ifNone(self.config["shuffle"], False))
        self.use_initial_weights.set(ifNone(self.config["use_initial_weights"], False))
        self.queryPreds.set(ifNone(self.config["query_preds"], ''))
        self.evidencePreds.set(ifNone(self.config["evidence_preds"], ''))
        self.discrPredicates.set(ifNone(self.config["discr_preds"], 0)) 
        self.selected_logic.set(ifNone(self.config['logic'], 'FirstOrderLogic')) 
        self.selected_grammar.set(ifNone(self.config['grammar'], 'PRACGrammar'))
        self.use_multiCPU.set(ifNone(self.config['multicore'], False))


    def learn(self, saveGeometry=True):
        window_loc = self.master.winfo_geometry()
        try:
            # update settings
            mln = self.selected_mln.get()
            db = self.selected_db.get()
            if mln == "":
                raise Exception("No MLN was selected")
            method = self.selected_method.get()
            params = self.params.get()
            
            self.config = PRACMLNConfig(os.path.join(self.dir.get(), learn_config_pattern % mln))
            self.config["mln"] = mln
            self.config["db"] = db
            self.config["output_filename"] = self.output_filename.get()
            self.config["params"] = params
            self.config["method"] = method
            self.config["pattern"] = self.pattern.get()
            self.config["use_prior"] = int(self.use_prior.get())
            # for incremental learning
            self.config["prior_mean"] = self.priorMean.get()
            self.config["prior_stdev"] = self.priorStdDev.get()
            self.config["incremental"] = int(self.incremental.get())
            self.config["shuffle"] = int(self.shuffle.get())
            self.config["use_initial_weights"] = int(self.use_initial_weights.get())

            self.config["query_preds"] = self.queryPreds.get()
            self.config["evidence_preds"] = self.evidencePreds.get()
            self.config["discr_preds"] = self.discrPredicates.get()
            self.config['logic'] = self.selected_logic.get()
            self.config['grammar'] = self.selected_grammar.get()
            self.config['multicore'] = self.use_multiCPU.get()
            
            # write settings
            logger.debug('writing config...')
            self.gconf['prev_learnwts_path'] = self.dir.get()
            self.gconf['prev_learnwts_mln':self.dir.get()] = self.selected_mln.get()
            self.gconf['window_loc_learn'] = window_loc
            self.gconf.dump()
            self.config.dump()
            
            # hide gui
            self.master.withdraw()
            
            # invoke learner
#             self.learner.run(params=params, method=method, **self.settings)
            
        except:
            cls, e, tb = sys.exc_info()
            logging.exception("%s: %s\n" % (str(e.__class__.__name__), str(e)))
#             traceback.print_tb(tb)
#             raise
        finally:
            # restore gui
            self.master.deiconify()
            self.set_window_loc(window_loc)
            sys.stdout.flush()

# -- main app --

if __name__ == '__main__':
    praclog.level(praclog.DEBUG)
    
    # read command-line options
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("--run", action="store_true", dest="run", default=False, help="run last configuration without showing gui")
    parser.add_option("-i", "--mln-filename", dest="mln_filename", help="input MLN filename", metavar="FILE", type="string")
    parser.add_option("-t", "--db-filename", dest="db", help="training database filename", metavar="FILE", type="string")
    parser.add_option("-o", "--output-file", dest="output_filename", help="output MLN filename", metavar="FILE", type="string")
    (options, args) = parser.parse_args()

    # run learning task/GUI
    root = Tk()
    gconf = PRACMLNConfig()
    app = MLNLearnGUI(root, gconf, directory=args[0] if args else None)
    #print "options:", options
    if options.run:
        app.learn(saveGeometry=False)
    else:
        out(gconf['window_loc_learn'])
        app.set_window_loc(gconf['window_loc_learn'])
        root.mainloop()

