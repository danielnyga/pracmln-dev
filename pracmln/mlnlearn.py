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
import StringIO

from Tkinter import *
from Tkinter import _setit
import sys
import ntpath
import traceback
from pracmln.mln.base import parse_mln
from pracmln.utils.project import MLNProject, mlnpath
from utils.widgets import *
import tkMessageBox
import fnmatch
from mln.methods import LearningMethods
from cProfile import Profile
from pracmln.utils import config
from pracmln.mln.util import ifNone, out, headline, StopWatch
from tkFileDialog import askdirectory, asksaveasfilename, askopenfilename
from pracmln.utils.config import PRACMLNConfig, global_config_filename
from pracmln import praclog, MLN
from tabulate import tabulate
import pstats
from pracmln.mln.database import Database, parse_db
from pracmln.mln.learning.common import DiscriminativeLearner

logger = praclog.logger(__name__)


QUERY_PREDS = 0
EVIDENCE_PREDS = 1
DEFAULTNAME = 'unknown{}'
PRACMLN_HOME = os.getenv('PRACMLN_HOME', os.getcwd())
DEFAULT_CONFIG = os.path.join(PRACMLN_HOME, global_config_filename)
WINDOWTITLE = 'PRACMLN Learning Tool - {}' + os.path.sep + '{}'
WINDOWTITLEEDITED = 'PRACMLN Learning Tool - {}' + os.path.sep + '*{}'

class MLNLearn(object):
    """
    Wrapper class for learning using a PRACMLN configuration.
    
    :param config: Instance of a :class:`pracmln.PRACMLNConfig` class representing a serialized 
                   configuration. Any parameter in the config object can be overwritten by a respective
                   entry in the ``params`` dict.
                   
    :example:
    
        >>> conf = PRACMLNConfig('path/to/config/file')
        >>> learn = MLNLearn(conf, mln=newmln, db=newdb) # overrides the MLN and database to be used.
    
    .. seealso::
        :class:`pracmln.PRACMLNConfig`
    
    """
    
    def __init__(self, config=None, **params):
        if config is None:
            self._config = {}
        else:
            self._config = config
        self._config.config.update(params)
        
    
    @property
    def mln(self):
        """
        The :class:`pracmln.MLN` instance to be used for learning.
        """
        return self._config.get('mln')
    
    
    @property
    def db(self):
        """
        The :class:`pracmln.Database` instance to be used for learning.
        """
        return  self._config.get('db')
    
    
    @property
    def output_filename(self):
        """
        The name of the file the learnt MLN is to be saved to.
        """
        return self._config.get('output_filename')
    
    
    @property
    def params(self):
        """
        A dictionary of additional parameters that are specific to a particular learning algorithm.
        """
        return eval("dict(%s)" % self._config.get('params', ''))
        
        
    @property
    def method(self):
        """
        The string identifier of the learning method to use. Defaults to ``'BPLL'``.
        """
        return LearningMethods.clazz(self._config.get('method', 'BPLL'))
        
        
    @property
    def pattern(self):
        """
        A Unix file pattern determining the database files for learning.
        """
        return self._config.get('pattern', '')
    
    
    @property
    def use_prior(self):
        """
        Boolean specifying whether or not to use a prio distribution for parameter learning. Defaults to ``False``
        """
        return self._config.get('use_prior', False) 
    

    @property
    def prior_mean(self):
        """
        The mean of the gaussian prior on the weights. Defaults to ``0.0``.
        """
        return float(self._config.get('prior_mean', 0.0))
    
    
    @property
    def prior_stdev(self):
        """
        The standard deviation of the prior on the weights. Defaults to ``5.0``.
        """
        return float(self._config.get('prior_stdev', 5.0))
    
    
    @property
    def incremental(self):
        """
        Specifies whether or incremental learning shall be enabled. Defaults to ``False``.
        
        .. note::
            This parameter is currently unused.
            
        """
        return self._config.get('incremental', False)


    @property
    def shuffle(self):
        """
        Specifies whether or not learning databases shall be shuffled before learning.
        
        .. note::
            This parameter is currently unused.
        """
        self._config.get('shuffle', False)
        
        
    @property
    def use_initial_weights(self):
        """
        Specifies whether or not the weights of the formulas prior to learning shall be used as
        an initial guess for the optimizer. Default is ``False``.
        """
        return self._config.get('use_initial_weights', False)
    
    
    @property
    def qpreds(self):
        """
        A list of predicate names specifying the query predicates in discriminative learning.
        
        .. note::
            This parameters only affects discriminative learning methods and is mutually exclusive
            with the :attr:`pracmln.MLNLearn.epreds` parameter.
        """
        return self._config.get('qpreds', '').split(',')

    
    @property
    def epreds(self):
        """
        A list of predicate names specifying the evidence predicates in discriminative learning.
        
        .. note::
            This parameters only affects discriminative learning methods and is mutually exclusive
            with the :attr:`pracmln.MLNLearn.qpreds` parameter.
        """
        return self._config.get('epreds', '').split(',')

    
    @property
    def discr_preds(self):
        """
        Specifies whether the query predicates or the evidence predicates shall be used. In either case,
        the respective other case will be automatically determined, i.e. if a list of query predicates
        is specified and ``disc_preds`` is ``pracmln.QUERY_PREDS``, then all other predicates
        will represent the evidence predicates and vice versa. Possible values are ``pracmln.QUERY_PREDS``
        and ``pracmln.EVIDENCE_PREDS``.
        """
        return self._config.get('discr_preds', QUERY_PREDS)
    

    @property
    def logic(self):
        """
        String identifying the logical calculus to be used in the MLN. Must be either ``'FirstOrderLogic'``
        or ``'FuzzyLogic'``.
        
        .. note::
            It is discouraged to use the ``FuzzyLogic`` calculus for learning MLNs. Default is ``'FirstOrderLogic'``. 
        """        
        return self._config.get('logic', 'FirstOrderLogic')
    
    
    @property
    def grammar(self):
        """
        String identifying the MLN syntax to be used. Allowed values are ``'StandardGrammar'`` and
        ``'PRACGrammar'``. Default is ``'PRACGrammar'``.
        """
        return self._config.get('grammar', 'PRACGrammar')
    
    
    @property
    def multicore(self):
        """
        Specifies if all cores of the CPU are to be used for learning. Default is ``False``.
        """
        return self._config.get('multicore', False) 

    
    @property
    def profile(self):
        """
        Specifies whether or not the Python profiler shall be used. This is convenient for debugging
        and optimizing your code in case you have developed own algorithms. Default is ``False``. 
        """
        return self._config.get('profile', False)
    
    
    @property
    def verbose(self):
        """
        If ``True``, prints some useful output, status and progress information to the console. Default is ``False``.
        """
        return self._config.get('verbose', False)
    
    
    @property
    def ignore_unknown_preds(self):
        """
        By default, if an atom occurs in a database that is not declared in the attached MLN, `pracmln` will raise
        a :class:`NoSuchPredicateException`. If ``ignore_unknown_preds`` is ``True``, undeclared predicates will
        just be ignored. 
        """
        return self._config.get('ignore_unknown_preds', False)
    
    @property
    def ignore_zero_weight_formulas(self):
        """
        When formulas in MLNs get more complex, there might be the chance that some of the formulas retain a weight of
        zero (because of strong independence assumptions in the Learner, for instance). Since such formulas have no
        effect on the semantics of an MLN but on the runtime of inference, they can be omitted in the final learnt
        MLN by settings ``ignore_zero_weight_formulas`` to ``True``.
        """
        return self._config.get('ignore_zero_weight_formulas', False)


    @property
    def save(self):
        """
        Specifies whether or not the learnt MLN shall be saved to a file.
        
        .. seealso::
            :attr:`pracmln.MLNLearn.output_filename`
        """        
        return self._config.get('save', False)
         


    def run(self):
        """
        Run the MLN learning with the given parameters.
        """
        # load the MLN
        if isinstance(self.mln, MLN):
            mln = self.mln
        else:
            raise Exception('No MLN specified')

        # load the training databases
        if type(self.db) is list and all(map(lambda e: isinstance(e, Database), self.db)):
            dbs = self.db
        elif isinstance(self.db, Database):
            dbs = [self.db]
        elif isinstance(self.db, basestring):
            db = self.db
            if db is None or not db:
                raise Exception('no trainig data given!')
            dbpaths = [os.path.join(self.directory, 'db', db)]
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
        # icon = Tkinter.Image("photo", file=os.path.join(PRACMLN_HOME, 'doc', '_static', 'favicon.ico'))
        # self.master.tk.call('wm', 'iconphoto', self.master._w, icon)

        self.initialized = False
        
        self.master.bind('<Return>', self.learn)
        self.master.bind('<Escape>', lambda a: self.master.quit())
        self.master.protocol('WM_DELETE_WINDOW', self.quit)

        # logo = Label(self.master, image=img)
        # logo.pack(side = "right", anchor='ne')

        self.frame = Frame(master)
        self.frame.pack(fill=BOTH, expand=1)
        self.frame.columnconfigure(1, weight=1)

        row = 0
        # pracmln project options
        Label(self.frame, text='PRACMLN Project: ').grid(row=row, column=0, sticky='ES')
        project_container = Frame(self.frame)
        project_container.grid(row=row, column=1, sticky="NEWS")

        # new proj file
        self.btn_newproj = Button(project_container, text='New Project...', command=self.new_project)
        self.btn_newproj.grid(row=0, column=1, sticky="WS")

        # open proj file
        self.btn_openproj = Button(project_container, text='Open Project...', command=self.ask_load_project)
        self.btn_openproj.grid(row=0, column=2, sticky="WS")

        # save proj file
        self.btn_saveproj = Button(project_container, text='Save Project', command=self.noask_save_project)
        self.btn_saveproj.grid(row=0, column=3, sticky="WS")

        # save proj file as...
        self.btn_saveproj = Button(project_container, text='Save Project as...', command=self.ask_save_project)
        self.btn_saveproj.grid(row=0, column=4, sticky="WS")

        # grammar selection
        row += 1
        Label(self.frame, text='Grammar: ').grid(row=row, column=0, sticky='E')
        grammars = ['StandardGrammar', 'PRACGrammar']
        self.selected_grammar = StringVar(master)
        self.selected_grammar.trace('w', self.select_grammar)
        l = apply(OptionMenu, (self.frame, self.selected_grammar) + tuple(grammars))
        l.grid(row=row, column=1, sticky='NWE')
        
        # logic selection
        row += 1
        Label(self.frame, text='Logic: ').grid(row=row, column=0, sticky='E')
        logics = ['FirstOrderLogic', 'FuzzyLogic']
        self.selected_logic = StringVar(master)
        self.selected_logic.trace('w', self.select_logic)
        l = apply(OptionMenu, (self.frame, self.selected_logic) + tuple(logics))
        l.grid(row=row, column=1, sticky='NWE')

        # mln selection
        row += 1
        Label(self.frame, text="MLN: ").grid(row=row, column=0, sticky='E')
        mln_container = Frame(self.frame)
        mln_container.grid(row=row, column=1, sticky="NEWS")
        mln_container.columnconfigure(1, weight=2)

        self.selected_mln = StringVar(master)
        mlnfiles = []
        self.mln_buffer = {}
        self._dirty_mln_name = ''
        self._mln_editor_dirty = False
        self.mln_reload = True
        if len(mlnfiles) == 0: mlnfiles.append("")
        self.list_mlns = apply(OptionMenu, (mln_container, self.selected_mln) + tuple(mlnfiles))
        self.list_mlns.grid(row=0, column=1, sticky="NWE")
        self.selected_mln.trace("w", self.select_mln)

        # new mln file
        self.btn_newmln = Button(mln_container, text='New', command=self.new_mln)
        self.btn_newmln.grid(row=0, column=2, sticky="E")

        # import mln file
        self.btn_importmln = Button(mln_container, text='Import', command=self.import_mln)
        self.btn_importmln.grid(row=0, column=3, sticky="E")

        # delete mln file
        self.btn_delmln = Button(mln_container, text='Delete', command=self.delete_mln)
        self.btn_delmln.grid(row=0, column=4, sticky="E")

        # mln filename field & save button
        self.mln_filename = StringVar(master, value='filename.mln')
        self.save_edit_mln = Entry(mln_container, textvariable=self.mln_filename)
        self.save_edit_mln.grid(row=0, column=5, sticky="E")

        self.btn_updatemln = Button(mln_container, text='Update', command=self.update_mln)
        self.btn_updatemln.grid(row=0, column=6, sticky="E")

        # mln editor
        row += 1
        self.mln_editor = SyntaxHighlightingText(self.frame, change_hook=self.onchange_mlncontent)
        self.mln_editor.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # method selection
        row += 1
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        methodnames = sorted(LearningMethods.names())
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methodnames))
        self.list_methods.grid(row=row, column=1, sticky="NWE")
        self.selected_method.trace("w", self.select_method)
        
        # additional parametrization
        row += 1
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        
        # use prior
        self.use_prior = IntVar()
        self.cb_use_prior = Checkbutton(frame, text="use prior with mean of ", variable=self.use_prior, command=self.onchange_useprior)
        self.cb_use_prior.pack(side=LEFT)
        
        # set prior 
        self.priorMean = StringVar(master)        
        self.en_prior_mean = Entry(frame, textvariable=self.priorMean, width=5)
        self.en_prior_mean.pack(side=LEFT)
        self.priorMean.trace('w', self.settings_setdirty)
        Label(frame, text="and std dev of").pack(side=LEFT)
        
        # std. dev.
        self.priorStdDev = StringVar(master)
        self.en_stdev = Entry(frame, textvariable = self.priorStdDev, width=5)
        self.priorStdDev.trace('w', self.settings_setdirty)
        self.en_stdev.pack(side=LEFT)
        
        # use initial weights in MLN 
        self.use_initial_weights = IntVar()
        self.cb_use_initial_weights = Checkbutton(frame, text="use initial weights", variable=self.use_initial_weights, command=self.settings_setdirty)
        self.cb_use_initial_weights.pack(side=LEFT)
        
        # use incremental learning
        self.incremental = IntVar()
        self.cb_incremental = Checkbutton(frame, text="learn incrementally", variable=self.incremental, command=self.onchange_incremental)
        self.cb_incremental.pack(side=LEFT)

        # shuffle databases
        self.shuffle = IntVar()
        self.cb_shuffle = Checkbutton(frame, text="shuffle databases", variable=self.shuffle, state='disabled')
        self.cb_shuffle.pack(side=LEFT)

        # discriminative learning settings
        row += 1
        self.discrPredicates = IntVar()
        self.discrPredicates.trace('w', self.change_discr_preds)
        self.discrPredicates.set(1)
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

        # db selection
        row += 1
        Label(self.frame, text="Training data: ").grid(row=row, column=0, sticky='E')
        db_container = Frame(self.frame)
        db_container.grid(row=row, column=1, sticky="NEWS")
        db_container.columnconfigure(1, weight=2)

        self.selected_db = StringVar(master)
        dbfiles = []
        self.db_buffer = {}
        self._dirty_db_name = ''
        self._db_editor_dirty = False
        self.db_reload = True
        if len(dbfiles) == 0: dbfiles.append("")
        self.list_dbs = apply(OptionMenu, (db_container, self.selected_db) + tuple(dbfiles))
        self.list_dbs.grid(row=0, column=1, sticky="NWE")
        self.selected_db.trace("w", self.select_db)

        # new db file
        self.btn_newdb = Button(db_container, text='New', command=self.new_db)
        self.btn_newdb.grid(row=0, column=2, sticky="W")

        # import db file
        self.btn_importdb = Button(db_container, text='Import', command=self.import_db)
        self.btn_importdb.grid(row=0, column=3, sticky="W")

        # delete db file
        self.btn_deldb = Button(db_container, text='Delete', command=self.delete_db)
        self.btn_deldb.grid(row=0, column=4, sticky="W")

        # db filename field & save button
        self.db_filename = StringVar(master, value='filename.db')
        self.save_edit_db = Entry(db_container, textvariable=self.db_filename)
        self.save_edit_db.grid(row=0, column=5, sticky="WE")

        self.btn_updatedb = Button(db_container, text='Update', command=self.update_db)
        self.btn_updatedb.grid(row=0, column=6, sticky="E")

        # db editor
        row += 1
        self.db_editor = SyntaxHighlightingText(self.frame, change_hook=self.onchange_dbcontent)
        self.db_editor.grid(row=row, column=1, sticky="NWES")
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
        self.pattern.trace('w', self.onchange_pattern)
        self.entry_pattern = Entry(frame, textvariable=self.pattern)
        self.entry_pattern.grid(row=0, column=col, sticky="NEW")

        # add. parameters
        row += 1
        Label(self.frame, text="Add. Params: ").grid(row=row, column=0, sticky="E")
        self.params = StringVar(master)
        Entry(self.frame, textvariable = self.params).grid(row=row, column=1, sticky="NEW")
        
        # options
        row += 1
        Label(self.frame, text="Options: ").grid(row=row, column=0, sticky="E")
        option_container = Frame(self.frame)
        option_container.grid(row=row, column=1, sticky="NEWS")

        # multicore
        self.multicore = IntVar()
        self.cb_multicore = Checkbutton(option_container, text="Use all CPUs", variable=self.multicore, command=self.settings_setdirty)
        self.cb_multicore.grid(row=0, column=1, sticky=E)

        # profiling
        self.profile = IntVar()
        self.cb_profile = Checkbutton(option_container, text='Use Profiler', variable=self.profile, command=self.settings_setdirty)
        self.cb_profile.grid(row=0, column=3, sticky=W)

        # verbose
        self.verbose = IntVar()
        self.cb_verbose = Checkbutton(option_container, text='verbose', variable=self.verbose, command=self.settings_setdirty)
        self.cb_verbose.grid(row=0, column=4, sticky=W)

        self.ignore_zero_weight_formulas = IntVar()
        self.cb_ignore_zero_weight_formulas = Checkbutton(option_container, text='remove 0-weight formulas', variable=self.ignore_zero_weight_formulas, command=self.settings_setdirty)
        self.cb_ignore_zero_weight_formulas.grid(row=0, column=5, sticky=W)

        # ignore unknown preds
        self.ignore_unknown_preds = IntVar(master)
        self.ignore_unknown_preds.trace('w', self.settings_setdirty)
        self.cb_ignore_unknown_preds = Checkbutton(option_container, text='ignore unkown predicates', variable=self.ignore_unknown_preds)
        self.cb_ignore_unknown_preds.grid(row=0, column=6, sticky="W")

        row += 1
        output_cont = Frame(self.frame)
        output_cont.grid(row=row, column=1, sticky='NEWS')
        output_cont.columnconfigure(0, weight=1)
        
        Label(self.frame, text="Output: ").grid(row=row, column=0, sticky="E")
        self.output_filename = StringVar(master)
        self.entry_output_filename = Entry(output_cont, textvariable=self.output_filename)
        self.entry_output_filename.grid(row=0, column=0, sticky="EW")
        
        self.save = IntVar(self.master)
        self.cb_save = Checkbutton(output_cont, text='save', variable=self.save)
        self.cb_save.grid(row=0, column=1, sticky='W')
        
        row += 1
        learn_button = Button(self.frame, text=" >> Start Learning << ", command=self.learn)
        learn_button.grid(row=row, column=1, sticky="EW")

        self.settings_dirty = IntVar()
        self.project_dirty = IntVar()

        self.gconf = gconf
        self.project = None
        self.dir = os.path.abspath(ifNone(gconf['prev_learnwts_path'], DEFAULT_CONFIG))
        self.project_dir = os.path.abspath(ifNone(gconf['prev_learnwts_path'], DEFAULT_CONFIG))
        if gconf['prev_learnwts_project': self.project_dir] is not None:
            self.load_project(os.path.join(self.project_dir, gconf['prev_learnwts_project': self.project_dir]))
        else:
            self.new_project()
        self.config = self.project.learnconf
        self.project.addlistener(self.project_setdirty)

        self.master.geometry(gconf['window_loc_learn'])
        
        self.initialized = True


    def quit(self):
        if self.settings_dirty.get() or self.project_dirty.get():
            savechanges = tkMessageBox.askyesnocancel("Save changes", "You have unsaved project changes. Do you want to save them before quitting?")
            if savechanges is None: return
            elif savechanges:
                self.noask_save_project()
            self.master.destroy()
        else:
            # write gui settings and destroy
            self.write_gconfig()
            self.master.destroy()


    ####################### PROJECT FUNCTIONS #################################
    def new_project(self):
        self.project = MLNProject()
        self.project.addlistener(self.project_setdirty)
        self.project.name = DEFAULTNAME.format('.pracmln')
        self.reset_gui()
        self.set_config(self.project.learnconf)
        self.update_mln_choices()
        self.update_db_choices()
        self.settings_setdirty()


    def project_setdirty(self, isdirty, *args):
        self.project_dirty.set(isdirty or self.mln_buffer != {} or self.db_buffer != {})
        self.changewindowtitle()


    def settings_setdirty(self, *args):
        self.settings_dirty.set(1)
        self.changewindowtitle()


    def changewindowtitle(self):
        title = (WINDOWTITLEEDITED if (self.settings_dirty.get() or self.project_dirty.get()) else WINDOWTITLE).format(self.project_dir, self.project.name)
        self.master.title(title)


    def ask_load_project(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('PRACMLN project files', '.pracmln')], defaultextension=".pracmln")
        if filename and os.path.exists(filename):
            self.load_project(filename)
        else:
            logger.info('No file selected.')
            return


    def load_project(self, filename):
        if filename and os.path.exists(filename):
            projdir, _ = ntpath.split(filename)
            self.dir = os.path.abspath(projdir)
            self.project_dir = os.path.abspath(projdir)
            self.project = MLNProject.open(filename)
            self.project.addlistener(self.project_setdirty)
            self.reset_gui()
            self.set_config(self.project.learnconf.config)
            self.update_mln_choices()
            self.update_db_choices()
            if len(self.project.mlns) > 0:
                self.selected_mln.set(self.project.learnconf['mln'] or self.project.mlns.keys()[0])
            if len(self.project.dbs) > 0:
                self.selected_db.set(self.project.learnconf['db'] or self.project.dbs.keys()[0])
            self.settings_dirty.set(0)
            self.project_setdirty(False)
        else:
            logger.error('File {} does not exist. Creating new project...'.format(filename))
            self.new_project()


    def noask_save_project(self):
        if self.project.name and not self.project.name == DEFAULTNAME.format('.pracmln'):
            self.save_project(os.path.join(self.project_dir, self.project.name))
        else:
            self.ask_save_project()


    def ask_save_project(self):
        fullfilename = asksaveasfilename(initialdir=self.project_dir, confirmoverwrite=True, filetypes=[('PRACMLN project files', '.pracmln')], defaultextension=".pracmln")
        self.save_project(fullfilename)


    def save_project(self, fullfilename):
        if fullfilename:
            fpath, fname = ntpath.split(fullfilename)
            fname = fname.split('.')[0]
            self.project.name = fname
            self.dir = os.path.abspath(fpath)
            self.project_dir = os.path.abspath(fpath)
            self.save_all_mlns()
            self.save_all_dbs()
            self.update_config()
            self.project.save(dirpath=self.project_dir)
            self.write_gconfig()
            self.load_project(fullfilename)
            self.settings_dirty.set(0)


    ####################### MLN FUNCTIONS #####################################
    def new_mln(self):
        self.project.add_mln(DEFAULTNAME.format('.mln'), content='')
        self.update_mln_choices()
        self.selected_mln.set(DEFAULTNAME.format('.mln'))


    def import_mln(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('MLN files', '.mln')], defaultextension=".mln")
        if filename:
            fpath, fname = ntpath.split(filename)
            self.dir = os.path.abspath(fpath)
            content = mlnpath(filename).content
            self.project.add_mln(fname, content)
            self.update_mln_choices()
            self.selected_mln.set(fname)


    def delete_mln(self):
        fname = self.selected_mln.get().strip()
        fnamestr = fname.strip('*')

        # remove element from project mlns and buffer
        if fname in self.mln_buffer:
            del self.mln_buffer[fname]
        if fname in self.project.mlns:
            self.project.rm_mln(fname)
        if fnamestr in self.project.mlns:
            self.project.rm_mln(fnamestr)
        self.update_mln_choices()

        # select first element from remaining list
        if len(self.project.mlns) > 0:
            self.selected_mln.set(self.project.mlns.keys()[0])
        else:
            self.selected_mln.set('')
            self.mln_editor.delete("1.0", END)
            self.mln_filename.set('')
            self.list_mlns['menu'].delete(0, 'end')


    def save_all_mlns(self):
        current = self.selected_mln.get().strip()
        for mln in self.mln_buffer:
            mlnstr = mln.strip('*')
            content = self.mln_buffer[mln]
            if mln == current:
                content = self.mln_editor.get("1.0", END).strip()
                out(content)
            if mlnstr in self.project.mlns:
                self.project.rm_mln(mlnstr)
            self.project.add_mln(mlnstr, content)

        # reset buffer, dirty flag for editor and update mln selections
        self.mln_buffer.clear()
        self._mln_editor_dirty = False
        self.update_mln_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        self.project_setdirty(False)


    def update_mln(self):
        oldfname = self.selected_mln.get().strip()
        newfname = self.mln_filename.get().strip()
        content = self.mln_editor.get("1.0", END).strip()

        if oldfname:
            if oldfname in self.mln_buffer:
                del self.mln_buffer[oldfname]
            if oldfname == newfname:
                self.project.mlns[oldfname] = content
            else:
                if oldfname in self.project.mlns:
                    self.project.rm_mln(oldfname)
                if newfname != '':
                    self.project.add_mln(newfname, content)

        # reset dirty flag for editor and update mln selections
        self._mln_editor_dirty = False
        self.update_mln_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        if newfname != '': self.selected_mln.set(newfname)
        self.project_setdirty(False)


    def select_mln(self, *args):
        mlnname = self.selected_mln.get().strip()
        self.project_setdirty(True)

        if mlnname is not None and mlnname != '':
            # filename is neither None nor empty
            if self._mln_editor_dirty:
                # save current state to buffer before updating editor
                self.mln_buffer[self._dirty_mln_name] = self.mln_editor.get("1.0", END).strip()
                self._mln_editor_dirty = True if '*' in mlnname else False
                if not self.mln_reload:
                    self.mln_reload = True
                    return
            if '*' in mlnname:# is edited
                # load previously edited content from buffer instead of mln file in project
                content = self.mln_buffer.get(mlnname, '').strip()
                self.mln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.mln_editor.insert(INSERT, content)
                self.mln_filename.set(mlnname.lstrip('*'))
                self.set_outputfilename()
                self._mln_editor_dirty = True
                self._dirty_mln_name = '*' + mlnname if '*' not in mlnname else mlnname
                return
            if mlnname in self.project.mlns:
                # load content from mln file in project
                content = self.project.mlns.get(mlnname, '').strip()
                self.mln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.mln_editor.insert(INSERT, content)
                self.mln_filename.set(mlnname)
                self.set_outputfilename()
                self._mln_editor_dirty = False
        else:
            # should not happen
            self.mln_editor.delete("1.0", END)
            self.mln_filename.set('')
            self.list_mlns['menu'].delete(0, 'end')


    def update_mln_choices(self):
        self.list_mlns['menu'].delete(0, 'end')

        new_mlns = sorted([i for i in self.project.mlns.keys() if '*'+i not in self.mln_buffer] + self.mln_buffer.keys())
        for mln in new_mlns:
            self.list_mlns['menu'].add_command(label=mln, command=_setit(self.selected_mln, mln))


    def onchange_mlncontent(self, *args):
        if not self._mln_editor_dirty:
            self._mln_editor_dirty = True
            self.mln_reload = False
            fname = self.selected_mln.get().strip()
            fname = '*' + fname if '*' not in fname else fname
            self._dirty_mln_name = fname
            self.mln_buffer[self._dirty_mln_name] = self.mln_editor.get("1.0", END).strip()
            self.update_mln_choices()
            self.selected_mln.set(self._dirty_mln_name)


    ####################### DB FUNCTIONS ######################################
    def new_db(self):
        self.project.add_db(DEFAULTNAME.format('.db'), content='')
        self.update_db_choices()
        self.selected_db.set(DEFAULTNAME.format('.db'))


    def import_db(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('Database files', '.db')], defaultextension=".db")
        if filename:
            fpath, fname = ntpath.split(filename)
            self.dir = os.path.abspath(fpath)
            content = mlnpath(filename).content
            self.project.add_db(fname, content)
            self.update_db_choices()
            self.selected_db.set(fname)


    def delete_db(self):
        fname = self.selected_db.get()
        fnamestr = fname.strip('*')

        # remove element from project dbs and buffer
        if fname in self.db_buffer:
            del self.db_buffer[fname]
        if fname in self.project.dbs:
            self.project.rm_db(fname)
        if fnamestr in self.project.dbs:
            self.project.rm_db(fnamestr)
        self.update_db_choices()

        # select first element from remaining list
        if len(self.project.dbs) > 0:
            self.selected_db.set(self.project.dbs.keys()[0])
        else:
            self.selected_db.set('')
            self.db_editor.delete("1.0", END)
            self.db_filename.set('')
            self.list_dbs['menu'].delete(0, 'end')


    def save_all_dbs(self):
        current = self.selected_db.get().strip()
        for db in self.db_buffer:
            dbstr = db.strip('*')
            content = self.db_buffer[db]
            if db == current:
                content = self.db_editor.get("1.0", END).strip()
            if dbstr in self.project.dbs:
                self.project.rm_db(dbstr)
            self.project.add_db(dbstr, content)

        # reset buffer, dirty flag for editor and update mln selections
        self.db_buffer.clear()
        self._db_editor_dirty = False
        self.update_db_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        self.project_setdirty(False)


    def update_db(self):
        oldfname = self.selected_db.get()
        newfname = self.db_filename.get()
        content = self.db_editor.get("1.0", END).strip()

        if oldfname.strip():
            if oldfname in self.db_buffer:
                del self.db_buffer[oldfname]
            if oldfname == newfname:
                self.project.dbs[oldfname] = content
            else:
                if oldfname in self.project.dbs:
                    self.project.rm_db(oldfname)
                if newfname != '':
                    self.project.add_db(newfname, content)

        # reset dirty flag for editor and update db selections
        self._db_editor_dirty = False
        self.update_db_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        if newfname != '': self.selected_db.set(newfname)
        self.project_setdirty(False)


    def select_db(self, *args):
        dbname = self.selected_db.get().strip()
        self.project_setdirty(True)

        if dbname is not None and dbname != '':
            # filename is neither None nor empty
            if self._db_editor_dirty:
                # save current state to buffer before updating editor
                self.db_buffer[self._dirty_db_name] = self.db_editor.get("1.0", END).strip()
                self._db_editor_dirty = True if '*' in dbname else False
                if not self.db_reload:
                    self.db_reload = True
                    return
            if '*' in dbname:# is edited
                # load previously edited content from buffer instead of db file in project
                content = self.db_buffer.get(dbname, '').strip()
                self.db_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.db_editor.insert(INSERT, content)
                self.db_filename.set(dbname.lstrip('*'))
                self.set_outputfilename()
                self._db_editor_dirty = True
                self._dirty_db_name = '*' + dbname if '*' not in dbname else dbname
                return
            if dbname in self.project.dbs:
                # load content from db file in project
                content = self.project.dbs.get(dbname, '').strip()
                self.db_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.db_editor.insert(INSERT, content)
                self.db_filename.set(dbname)
                self.set_outputfilename()
                self._db_editor_dirty = False
        else:
            # should not happen
            self.db_editor.delete("1.0", END)
            self.db_filename.set('')
            self.list_dbs['menu'].delete(0, 'end')


    def update_db_choices(self):
        self.list_dbs['menu'].delete(0, 'end')

        new_dbs = sorted([i for i in self.project.dbs.keys() if '*'+i not in self.db_buffer] + self.db_buffer.keys())
        for db in new_dbs:
            self.list_dbs['menu'].add_command(label=db, command=_setit(self.selected_db, db))


    def onchange_dbcontent(self, *args):
        if not self._db_editor_dirty:
            self._db_editor_dirty = True
            self.db_reload = False
            fname = self.selected_db.get().strip()
            fname = '*' + fname if '*' not in fname else fname
            self._dirty_db_name = fname
            self.db_buffer[self._dirty_db_name] = self.db_editor.get("1.0", END).strip()
            self.update_db_choices()
            self.selected_db.set(self._dirty_db_name)


    ####################### GENERAL FUNCTIONS #################################

    def onchange_incremental(self):
        if self.incremental.get()==1:
            self.cb_shuffle.configure(state="normal")  
        else:
            self.cb_shuffle.configure(state="disabled")
            self.cb_shuffle.deselect()
        self.settings_setdirty()

            
    def onchange_pattern(self, *args):
        self.list_dbs.config(state=DISABLED if self.pattern.get() else NORMAL)
        self.settings_setdirty()


    def onchange_useprior(self, *args):
        self.en_prior_mean.configure(state=NORMAL if self.use_prior.get() else DISABLED)
        self.en_stdev.configure(state=NORMAL if self.use_prior.get() else DISABLED)
        self.settings_setdirty()


    def isfile(self, f):
        return os.path.exists(os.path.join(self.dir, f))


    def set_outputfilename(self):
        if not hasattr(self, "output_filename") or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        mln = self.mln_filename.get()
        db = self.db_filename.get()
        if "" in (mln, db): return
        if self.selected_method.get():
            method = LearningMethods.clazz(self.selected_method.get())
            methodid = LearningMethods.id(method)
            filename = config.learnwts_output_filename(mln, methodid.lower(), db)
            self.output_filename.set(filename)
        

    def select_logic(self, *args):
        self.logic = self.selected_logic.get()
        self.settings_setdirty()

    
    def select_grammar(self, *args):
        self.grammar = self.selected_grammar.get()
        self.settings_setdirty()


    def select_method(self, *args):
        self.change_discr_preds()
        self.set_outputfilename()
        self.settings_setdirty()


    def change_discr_preds(self, *args):
        methodname = self.selected_method.get()
        if methodname:
            method = LearningMethods.clazz(methodname)
            state = NORMAL if issubclass(method, DiscriminativeLearner) else DISABLED
            self.entry_nePreds.configure(state=state if self.discrPredicates.get() == 0 else DISABLED)
            self.entryEvidencePreds.configure(state=state if self.discrPredicates.get() == 1 else DISABLED)
            self.rbEvidencePreds.configure(state=state)
            self.rbQueryPreds.configure(state=state)


    def reset_gui(self):
        self.db_buffer.clear()
        self.mln_buffer.clear()
        self.set_config({})
        self.mln_editor.delete("1.0", END)
        self.mln_filename.set('')
        self.db_editor.delete("1.0", END)
        self.db_filename.set('')


    def set_config(self, conf):
        self.config = conf
        self.selected_grammar.set(ifNone(conf.get('grammar'), 'PRACGrammar'))
        self.selected_logic.set(ifNone(conf.get('logic'), 'FirstOrderLogic'))
        self.selected_mln.set(ifNone(conf.get('mln'), ""))
        self.selected_db.set(ifNone(conf.get('db'), ""))
        self.selected_method.set(ifNone(conf.get("method"), LearningMethods.name('BPLL'), transform=LearningMethods.name))
        self.pattern.set(ifNone(conf.get('pattern'), ''))
        self.multicore.set(ifNone(conf.get('multicore'), 0))
        self.use_prior.set(ifNone(conf.get('use_prior'), 0))
        self.priorMean.set(ifNone(conf.get('prior_mean'), 0))
        self.priorStdDev.set(ifNone(conf.get('prior_stdev'), 5))
        self.incremental.set(ifNone(conf.get('incremental'), 0))
        self.shuffle.set(ifNone(conf.get('shuffle'), 0))
        self.use_initial_weights.set(ifNone(conf.get('use_initial_weights'), 0))
        self.profile.set(ifNone(conf.get('profile'), 0))
        self.params.set(ifNone(conf.get('params'), ''))
        self.verbose.set(ifNone(conf.get('verbose'), 1))
        self.ignore_unknown_preds.set(ifNone(conf.get('ignore_unknown_preds'), 0))
        self.output_filename.set(ifNone(conf.get('output_filename'), ''))
        self.queryPreds.set(ifNone(conf.get('qpreds'), ''))
        self.evidencePreds.set(ifNone(conf.get('epreds'), ''))
        self.discrPredicates.set(ifNone(conf.get('discr_preds'), 0))
        self.ignore_zero_weight_formulas.set(ifNone(conf.get('ignore_zero_weight_formulas'), 0))
        self.save.set(ifNone(conf.get('save'), 0))


    def get_training_db_paths(self, pattern):
        """
        determine training databases(s)
        """
        local = False
        dbs = []
        if pattern is not None and pattern.strip():
            fpath, pat = ntpath.split(pattern)
            if not os.path.exists(fpath):
                logger.debug('%s does not exist. Searching for pattern %s in project %s...' % (fpath, pat, self.project.name))
                local = True
                dbs = [db for db in self.project.dbs if fnmatch.fnmatch(db, pattern)]
                if len(dbs) == 0:
                    raise Exception("The pattern '%s' matches no files in your project %s" % (pat, self.project.name))
            else:
                local = False
                patternpath = os.path.join(self.dir, pattern)

                d, mask = os.path.split(os.path.abspath(patternpath))
                for fname in os.listdir(d):
                    print fname
                    if fnmatch.fnmatch(fname, mask):
                        dbs.append(os.path.join(d, fname))
                if len(dbs) == 0:
                    raise Exception("The pattern '%s' matches no files in %s" % (pat, fpath))
            logger.debug('loading training databases from pattern %s:' % pattern)
            for p in dbs: logger.debug('  %s' % p)
        if not dbs:
            raise Exception("No training data given; A training database must be selected or a pattern must be specified")
        else: return local, dbs


    def update_config(self):
        out('update_config')

        self.config = PRACMLNConfig()
        self.config["mln"] = self.selected_mln.get().strip().lstrip('*')
        self.config["db"] = self.selected_db.get().strip().lstrip('*')
        self.config["output_filename"] = self.output_filename.get()
        self.config["params"] = self.params.get().strip()
        self.config["method"] = LearningMethods.id(self.selected_method.get().strip())
        self.config["pattern"] = self.pattern.get()
        self.config["use_prior"] = int(self.use_prior.get())
        self.config["prior_mean"] = self.priorMean.get()
        self.config["prior_stdev"] = self.priorStdDev.get()
        self.config["incremental"] = int(self.incremental.get())
        self.config["shuffle"] = int(self.shuffle.get())
        self.config["use_initial_weights"] = int(self.use_initial_weights.get())
        self.config["qpreds"] = self.queryPreds.get().strip()
        self.config["epreds"] = self.evidencePreds.get().strip()
        self.config["discr_preds"] = self.discrPredicates.get()
        self.config['logic'] = self.selected_logic.get()
        self.config['grammar'] = self.selected_grammar.get()
        self.config['multicore'] = self.multicore.get()
        self.config['profile'] = self.profile.get()
        self.config['verbose'] = self.verbose.get()
        self.config['ignore_unknown_preds'] = self.ignore_unknown_preds.get()
        self.config['ignore_zero_weight_formulas'] = self.ignore_zero_weight_formulas.get()
        self.config['save'] = self.save.get()
        self.config["output_filename"] = self.output_filename.get().strip()
        self.project.learnconf = PRACMLNConfig()
        self.project.learnconf.update(self.config.config.copy())


    def update_project(self):
        self.update_mln()
        self.update_db()


    def write_gconfig(self, savegeometry=True):
        self.gconf['prev_learnwts_path'] = self.project_dir
        self.gconf['prev_learnwts_project': self.project_dir] = self.project.name

        # save geometry
        if savegeometry:
            self.gconf['window_loc_learn'] = self.master.geometry()
        self.gconf.dump()


    def learn(self, savegeometry=True, options={}, *args):
        mln_content = self.mln_editor.get("1.0", END).encode('utf8').strip()
        db_content = self.db_editor.get("1.0", END).encode('utf8').strip()

        # create conf from current gui settings
        self.update_config()

        # write gui settings
        self.write_gconfig(savegeometry=savegeometry)

        # hide gui
        self.master.withdraw()

        try:
            print headline('PRAC LEARNING TOOL')
            print

            if options.get('mlnarg') is not None:
                mlnobj = MLN(mlnfile=os.path.abspath(options.get('mlnarg')), logic=self.config.get('logic', 'FirstOrderLogic'), grammar=self.config.get('grammar', 'PRACGrammar'))
            else:
                mlnobj = parse_mln(mln_content, searchpaths=[self.project_dir], projectpath=os.path.join(self.project_dir, self.project.name), logic=self.config.get('logic', 'FirstOrderLogic'), grammar=self.config.get('grammar', 'PRACGrammar'))

            if options.get('dbarg') is not None:
                dbobj = Database.load(mlnobj, dbfile=options.get('dbarg'), ignore_unknown_preds=self.config.get('ignore_unknown_preds', True))
            else:
                if self.config.get('pattern'):
                    local, dblist = self.get_training_db_paths(self.config.get('pattern').strip())
                    dbobj = []
                    # build database list from project dbs
                    if local:
                        for dbname in dblist:
                            dbobj.extend(parse_db(mlnobj, self.project.dbs[dbname].strip(), ignore_unknown_preds=self.config.get('ignore_unknown_preds', True), projectpath=os.path.join(self.dir, self.project.name)))
                        out(dbobj)
                    # build database list from filesystem dbs
                    else:
                        for dbpath in dblist:
                            dbobj.extend(Database.load(mlnobj, dbpath, ignore_unknown_preds=self.config.get('ignore_unknown_preds', True)))
                # build single db from currently selected db
                else:
                    dbobj = parse_db(mlnobj, db_content, projectpath=os.path.join(self.dir, self.project.name), dirs=[self.dir])


            learning = MLNLearn(config=self.config, mln=mlnobj, db=dbobj)
            result = learning.run()

            # write to file if run from commandline, otherwise save result to project results
            if options.get('outputfile') is not None:
                output = StringIO.StringIO()
                result.write(output)
                with open(os.path.abspath(options.get('outputfile')), 'w') as f:
                    f.write(output.getvalue())
                logger.info('saved result to {}'.format(os.path.abspath(options.get('outputfile'))))
            elif self.save.get():
                output = StringIO.StringIO()
                result.write(output)
                self.project.add_mln(self.output_filename.get(), output.getvalue())
                self.update_mln_choices()
                self.project.save(dirpath=self.project_dir)
                logger.info('saved result to file mln/{} in project {}'.format(self.output_filename.get(), self.project.name))
            else:
                logger.debug('No output file given - results have not been saved.')

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
    parser.add_option("-i", "--mln-filename", dest="mlnarg", help="input MLN filename", metavar="FILE", type="string")
    parser.add_option("-t", "--db-filename", dest="dbarg", help="training database filename", metavar="FILE", type="string")
    parser.add_option("-o", "--output-file", dest="outputfile", help="output MLN filename", metavar="FILE", type="string")
    (opts, args) = parser.parse_args()
    options = vars(opts)

    # run learning task/GUI
    root = Tk()
    conf = PRACMLNConfig(DEFAULT_CONFIG)
    app = MLNLearnGUI(root, conf, directory=args[0] if args else None)

    if opts.run:
        logger.debug('running mlnlearn without gui')
        app.learn(savegeometry=False, options=options)
    else:
        root.mainloop()

