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
from pracmln.mln.util import ifNone, out, headline, StopWatch, stop
from tkMessageBox import showerror, askyesno
from tkFileDialog import askdirectory
from pracmln.utils.config import learn_config_pattern, PRACMLNConfig
from pracmln import praclog
from tabulate import tabulate
import pstats
from pracmln.mln.database import Database
from pracmln.mln.learning.common import DiscriminativeLearner

logger = praclog.logger(__name__)


QUERY_PREDS = 0
EVIDENCE_PREDS = 1


class MLNLearn(object):
    '''
    Wrapper class for learning using a PRACMLN configuration
    '''
    
    def __init__(self, config=None, **params):
        if config is None:
            self._config = {}
        else:
            self._config = config
        self._config.config.update(params)
        
    
    @property
    def mln(self):
        return self._config.get('mln')
    
    
    @property
    def db(self):
        return  self._config.get('db')
    
    
    @property
    def output_filename(self):
        return self._config.get('output_filename')
    
    
    @property
    def params(self):
        return eval("dict(%s)" % self._config.get('params', ''))
        
        
    @property
    def method(self):
        return LearningMethods.clazz(self._config.get('method', 'BPLL'))
        
        
    @property
    def pattern(self):
        return self._config.get('pattern', '')
    
    
    @property
    def use_prior(self):
        return self._config.get('use_prior', False) 
    

    @property
    def prior_mean(self):
        return float(self._config.get('prior_mean', 0))
    
    
    @property
    def prior_stdev(self):
        return float(self._config.get('prior_stdev', 5))
    
    
    @property
    def incremental(self):
        return self._config.get('incremental', False)


    @property
    def shuffle(self):
        self._config.get('shuffle', False)
        
        
    @property
    def use_initial_weights(self):
        return self._config.get('use_initial_weights', False)
    
    
    @property
    def qpreds(self):
        return self._config.get('qpreds', '').split(',')

    
    @property
    def epreds(self):
        return self._config.get('epreds', '').split(',')

    
    @property
    def discr_preds(self):
        return self._config.get('discr_preds', QUERY_PREDS)
    

    @property
    def logic(self):
        return self._config.get('logic', 'FirstOrderLogic')
    
    
    @property
    def grammar(self):
        return self._config.get('grammar', 'PRACGrammar')
    
    
    @property
    def multicore(self):
        return self._config.get('multicore', False) 

    
    @property
    def profile(self):
        return self._config.get('profile', False)
    
    
    @property
    def verbose(self):
        return self._config.get('verbose', False)
    
    
    @property
    def ignore_unknown_preds(self):
        return self._config.get('ignore_unknown_preds', False)
    
    @property
    def ignore_zero_weight_formulas(self):
        return self._config.get('ignore_zero_weight_formulas', False)


    @property
    def save(self):
        return self._config.get('save', False)
         
    
    @property
    def directory(self):
        return os.path.dirname(self._config.config_file)
    

    def get_training_db_paths(self):
        ''' 
        determine training databases(s) 
        '''
        pattern = self.pattern
        if pattern is not None and pattern.strip():
            dbs = []
            patternpath = os.path.join(self.directory, pattern)
            d, mask = os.path.split(os.path.abspath(patternpath))
            for fname in os.listdir(d):
                if fnmatch(fname, mask):
                    dbs.append(os.path.join(d, fname))
            if len(dbs) == 0:
                raise Exception("The pattern '%s' matches no files in %s" % (pattern, self.dir.get()))
            logger.debug('loading training databases from pattern %s:')
            for p in dbs: logger.debug('  %s' % p)
        if not dbs:
            raise Exception("No training data given; A training database must be selected or a pattern must be specified")
        else: return dbs   


    def run(self):
        '''
        Run the MLN learning with the given parameters.
        '''
        # load the MLN
        if isinstance(self.mln, MLN):
            mln = self.mln
        elif isinstance(self.mln, basestring):
            mlnfile = os.path.join(self.directory, self.mln)
            mln = MLN(mlnfile=mlnfile, logic=self.logic, grammar=self.grammar)

        # load the training databases
        if type(self.db) is list and all(map(lambda e: isinstance(e, Database))):
            dbs = self.db
        elif isinstance(self.db, Database):
            dbs = [self.db]
        elif self.pattern:
            dbpaths = self.get_training_db_paths()
            dbs = []
            for p in dbpaths:
                dbs.extend(Database.load(mln, p, self.ignore_unknown_preds))
        elif isinstance(self.db, basestring):
            db = self.db
            if db is None or not db:
                raise Exception('no trainig data given!')
            dbpaths = [os.path.join(self.directory, db)]
            dbs = []
            for p in dbpaths:
                dbs.extend(Database.load(mln, p, self.ignore_unknown_preds))
        else:
            raise Exception('Unexpected type of training databases: %s' % type(self.db))
        if self.verbose: print 'loaded %d database(s).' % len(dbs)
        
        watch = StopWatch()

        if self.verbose:
            conf = dict(self._config.config)
            conf.update(eval("dict(%s)" % self.params))
            print tabulate(sorted(list(conf.viewitems()), key=lambda (k,v): str(k)), headers=('Parameter:', 'Value:'))

        params = dict([(k, getattr(self, k)) for k in ('multicore', 'verbose', 'profile', 'ignore_zero_weight_formulas')])
        
        # for discriminative learning
        if issubclass(self.method, DiscriminativeLearner):
            if self.discr_preds == QUERY_PREDS: # use query preds
                params['qpreds'] = self.qpreds
            elif self.discr_preds == EVIDENCE_PREDS: # use evidence preds
                params['epreds'] = self.epreds
        
        # gaussian prior settings            
        if self.use_prior:
            params['prior_mean'] = self.prior_mean
            params['prior_stdev'] = self.prior_stdev
        # expand the parameters
        params.update(self.params)
        
        if self.profile:
            prof = Profile()
            print 'starting profiler...'
            prof.enable()
        # set the debug level
        olddebug = praclog.level()
        praclog.level(eval('logging.%s' % params.get('debug', 'WARNING').upper()))
        mlnlearnt = None
        try:
            # load the databases
            dbpaths = dbs
            
            # run the learner
            mlnlearnt = mln.learn(dbs, self.method, **params)
            if self.verbose:
                print 
                print headline('LEARNT MARKOV LOGIC NETWORK')
                print
                mlnlearnt.write()
            if self.save:
                with open(os.path.join(self.directory, self.output_filename), 'w+') as outFile:
                    mlnlearnt.write(outFile)
        except SystemExit:
            print 'Cancelled...'
        finally:
            if self.profile:
                prof.disable()
                print headline('PROFILER STATISTICS')
                ps = pstats.Stats(prof, stream=sys.stdout).sort_stats('cumulative')
                ps.print_stats()
            # reset the debug level
            praclog.level(olddebug)
        print
        watch.finish()
        watch.printSteps()
        return mlnlearnt
    

class MLNLearnGUI:


    def __init__(self, master, gconf, directory=None):
        self.master = master
        self.master.title("PRACMLN Learning Tool")
        
        self.initialized = False
        
        self.master.bind('<Return>', self.learn)
        self.master.bind('<Escape>', lambda a: self.master.quit())
        
        self.gconf = gconf
        self.config = None

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
                                         self.select_mln, rename_on_edit=0, 
                                         font=config.fixed_width_font, coloring=True)
        self.selected_mln.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # method selection
        row += 1
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        methodnames = sorted(LearningMethods.names())
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methodnames))
        self.list_methods.grid(row=row, column=1, sticky="NWE")
        self.selected_method.trace("w", self.changedMethod)
        
        # additional parametrization
        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        
        # use prior
        self.use_prior = IntVar()
        self.use_prior.trace('w', self.check_prior)
        self.cb_use_prior = Checkbutton(frame, text="use prior with mean of ", variable=self.use_prior)
        self.cb_use_prior.pack(side=LEFT)
        
        # set prior 
        self.priorMean = StringVar(master)        
        self.en_prior_mean = Entry(frame, textvariable=self.priorMean, width=5)
        self.en_prior_mean.pack(side=LEFT)
        Label(frame, text=" and std dev of ").pack(side=LEFT)
        
        # std. dev.
        self.priorStdDev = StringVar(master)
        self.en_stdev = Entry(frame, textvariable = self.priorStdDev, width=5)
        self.en_stdev.pack(side=LEFT)
        
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
        self.discrPredicates.trace('w', self.change_discr_preds)
        frame = Frame(self.frame)        
        frame.grid(row=row, column=1, sticky="NEWS")
        self.rbQueryPreds = Radiobutton(frame, text="Query preds:", variable=self.discrPredicates, value=QUERY_PREDS)
        self.rbQueryPreds.grid(row=0, column=0, sticky="NE")
                
        self.queryPreds = StringVar(master)
        frame.columnconfigure(1, weight=1)
        self.entry_nePreds = Entry(frame, textvariable = self.queryPreds)
        self.entry_nePreds.grid(row=0, column=1, sticky="NEW")        

        self.rbEvidencePreds = Radiobutton(frame, text='Evidence preds', variable=self.discrPredicates, value=EVIDENCE_PREDS)
        self.rbEvidencePreds.grid(row=0, column=2, sticky='NEWS')
        
        self.evidencePreds = StringVar(master)
        self.entryEvidencePreds = Entry(frame, textvariable=self.evidencePreds)
        self.entryEvidencePreds.grid(row=0, column=3, sticky='NEWS')


        # evidence database selection
        row += 1
        Label(self.frame, text="Training data: ").grid(row=row, column=0, sticky="NE")
        self.frame.rowconfigure(row, weight=1)
        
        self.selected_db = FilePickEdit(self.frame, config.learnwts_db_filemask, '', 15, self.changedDB, font=config.fixed_width_font)
        self.selected_db.grid(row=row, column=1, sticky="NEWS")
        
        # ignore unknown preds
        self.ignore_unknown_preds = IntVar(master)
        self.cb_ignore_unknown_preds = Checkbutton(self.selected_db.options_frame, text='ignore unkown predicates', variable=self.ignore_unknown_preds)
        self.cb_ignore_unknown_preds.pack(side=LEFT)
        

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
        self.pattern.trace('w', self.change_pattern)
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
        
        self.ignore_zero_weight_formulas = IntVar()
        self.cb_ignore_zero_weight_formulas = Checkbutton(option_container, text='remove 0-weight formulas', variable=self.ignore_zero_weight_formulas)
        self.cb_ignore_zero_weight_formulas.grid(row=0, column=5, sticky=W)

        row += 1
        output_cont = Frame(self.frame)
        output_cont.grid(row=row, column=1, sticky='NEWS')
        output_cont.columnconfigure(0, weight=1)
        
        Label(self.frame, text="Output filename: ").grid(row=row, column=0, sticky="E")
        self.output_filename = StringVar(master)
        
        Entry(output_cont, textvariable = self.output_filename).grid(row=0, column=0, sticky="EW")
        
        self.save = IntVar(self.master)
        self.cb_save = Checkbutton(output_cont, text='save', variable=self.save)
        self.cb_save.grid(row=0, column=1, sticky='W')
        
        row += 1
        learn_button = Button(self.frame, text=" >> Learn << ", command=self.learn)
        learn_button.grid(row=row, column=1, sticky="EW")

        self.set_dir(ifNone(directory, ifNone(gconf['prev_learnwts_path'], os.getcwd())))
        if gconf['prev_learnwts_mln':self.dir.get()] is not None:
            self.selected_mln.set(gconf['prev_learnwts_mln':self.dir.get()])
        
        self.master.geometry(gconf['window_loc_learn'])
        
        self.initialized = True


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
        if self.config is None or not self.initialized or \
            os.path.exists(confname) and askyesno('PRACMLN', 'A configuration file was found for the selected MLN.\nDo want to load the configuration?'):
            self.set_config(PRACMLNConfig(confname))
        self.mln_filename = mlnname
        self.setOutputFilename()
            
            
    def check_incremental(self):
        if self.incremental.get()==1:
            self.cb_shuffle.configure(state="normal")  
        else:
            self.cb_shuffle.configure(state="disabled")
            self.cb_shuffle.deselect()
            
            
    def change_pattern(self, *args):
        self.selected_db.set_enabled(state=DISABLED if self.pattern.get() else NORMAL)
                

    def check_prior(self, *args):
        self.en_prior_mean.configure(state=NORMAL if self.use_prior.get() else DISABLED)
        self.en_stdev.configure(state=NORMAL if self.use_prior.get() else DISABLED)
        

    def isFile(self, f):
        return os.path.exists(os.path.join(self.dir.get(), f))


    def setOutputFilename(self):
        if not hasattr(self, "output_filename") or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        mln = self.mln_filename
        db = self.db_filename
        if "" in (mln, db): return
        if self.selected_method.get():
            method = LearningMethods.clazz(self.selected_method.get())
            methodid = LearningMethods.id(method)
            filename = config.learnwts_output_filename(mln, methodid.lower(), db)
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
        self.change_discr_preds()
        
        
    def change_discr_preds(self, name = None, index = None, mode = None):
        methodname = self.selected_method.get()
        method = LearningMethods.clazz(methodname)
        state = NORMAL if issubclass(method, DiscriminativeLearner) else DISABLED
        self.entry_nePreds.configure(state=state if self.discrPredicates.get() == 0 else DISABLED)
        self.entryEvidencePreds.configure(state=state if self.discrPredicates.get() == 1 else DISABLED)
        self.rbEvidencePreds.configure(state=state)
        self.rbQueryPreds.configure(state=state)
        

    def changedMethod(self, name, index, mode):
        self.onChangeMethod()
        self.setOutputFilename()

    
    def get_training_db_paths(self):
        ''' 
        determine training databases(s) 
        '''
        pattern = self.config["pattern"]
        if pattern is not None and pattern.strip():
            dbs = []
            patternpath = os.path.join(self.dir.get(), pattern)
            d, mask = os.path.split(os.path.abspath(patternpath))
            for fname in os.listdir(d):
                if fnmatch(fname, mask):
                    dbs.append(os.path.join(d, fname))
            if len(dbs) == 0:
                raise Exception("The pattern '%s' matches no files in %s" % (pattern, self.dir.get()))
            logger.debug('loading training databases from pattern %s:')
            for p in dbs: logger.debug('  %s' % p)
        if not dbs:
            raise Exception("No training data given; A training database must be selected or a pattern must be specified")
        else: return dbs       


    def set_config(self, conf):
        self.config = conf
#         self.selected_db.set(ifNone(self.config["db"], ''))
        self.selected_grammar.set(ifNone(conf['grammar'], 'PRACGrammar'))
        self.selected_logic.set(ifNone(conf['logic'], 'FirstOrderLogic'))
        self.selected_db.select(ifNone(conf['db'], ''))
        self.output_filename.set(ifNone(self.config["output_filename"], ''))
        self.save.set(ifNone(self.config['save'], 1))
        self.params.set(ifNone(self.config["params"], ''))
        self.selected_method.set(ifNone(self.config["method"], LearningMethods.name('BPLL'), transform=LearningMethods.name))
        self.pattern.set(ifNone(self.config["pattern"], ''))
        self.use_prior.set(ifNone(self.config["use_prior"], False))
        self.priorMean.set(ifNone(self.config["prior_mean"], 0))
        self.priorStdDev.set(ifNone(self.config["prior_stdev"], 5))
        self.incremental.set(ifNone(self.config["incremental"], False))
        self.shuffle.set(ifNone(self.config["shuffle"], False))
        self.use_initial_weights.set(ifNone(self.config["use_initial_weights"], False))
        self.queryPreds.set(ifNone(self.config["qpreds"], ''))
        self.evidencePreds.set(ifNone(self.config["epreds"], ''))
        self.discrPredicates.set(ifNone(self.config["discr_preds"], 0)) 
        self.use_multiCPU.set(ifNone(self.config['multicore'], False))
        self.verbose.set(ifNone(conf['verbose'], 1))
        self.profile.set(ifNone(conf['profile'], False))
        self.ignore_unknown_preds.set(ifNone(conf['ignore_unknown_preds'], False))
        self.ignore_zero_weight_formulas.set(ifNone(conf['ignore_zero_weight_formulas'], False))


    def learn(self, *args):
        # update settings;
        mln = self.selected_mln.get().encode('utf8')
        db = self.selected_db.get().encode('utf8')
        if mln == "":
            raise Exception("No MLN was selected")
        methodname = self.selected_method.get().encode('utf8')
        params = self.params.get().encode('utf8')
        output = str(self.output_filename.get()).encode('utf8')
        self.config = PRACMLNConfig(os.path.join(self.dir.get(), learn_config_pattern % mln))
        self.config["mln"] = mln
        self.config["db"] = db
        self.config["output_filename"] = self.output_filename.get()
        self.config["params"] = params
        self.config["method"] = LearningMethods.id(methodname)
        self.config["pattern"] = self.pattern.get()
        self.config["use_prior"] = int(self.use_prior.get())
        self.config["prior_mean"] = self.priorMean.get()
        self.config["prior_stdev"] = self.priorStdDev.get()
        self.config["incremental"] = int(self.incremental.get())
        self.config["shuffle"] = int(self.shuffle.get())
        self.config["use_initial_weights"] = int(self.use_initial_weights.get())
        self.config["qpreds"] = self.queryPreds.get().encode('utf8')
        self.config["epreds"] = self.evidencePreds.get().encode('utf8')
        self.config["discr_preds"] = self.discrPredicates.get()
        self.config['logic'] = self.selected_logic.get()
        self.config['grammar'] = self.selected_grammar.get()
        self.config['multicore'] = self.use_multiCPU.get()
        self.config['profile'] = self.profile.get()
        self.config['verbose'] = self.verbose.get()
        self.config['ignore_unknown_preds'] = self.ignore_unknown_preds.get()
        self.config['ignore_zero_weight_formulas'] = self.ignore_zero_weight_formulas.get()
        self.config['save'] = self.save.get()
        
        # write settings
        logger.debug('writing config...')
        self.gconf['prev_learnwts_path'] = self.dir.get()
        self.gconf['prev_learnwts_mln':self.dir.get()] = self.selected_mln.get()
        self.gconf['window_loc_learn'] = self.master.geometry()
        self.gconf.dump()
        self.config.dump()
        
        # hide gui
        self.master.withdraw()
        
        try:
            learning = MLNLearn(self.config)
            learning.run()
        except:
            traceback.print_exc()
        # restore gui
        sys.stdout.flush()
        self.master.deiconify()

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
        root.mainloop()

