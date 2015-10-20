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
from Tkinter import _setit
import Tkinter
from tkFileDialog import askdirectory, askopenfile, askopenfilename, \
    asksaveasfilename
import os
import ntpath
import re
import tkMessageBox
import traceback
from pracmln.utils.project import MLNProject, mlnpath
from utils import widgets
from mln.methods import InferenceMethods
from mln.inference import *
from utils.widgets import FilePickEdit, DropdownList, SyntaxHighlightingText
from logic.grammar import StandardGrammar, PRACGrammar  # @UnusedImport
import logging
from utils import config
from pracmln import praclog
from tkMessageBox import showerror, askyesno
from pracmln.mln.util import out, ifNone, trace, parse_queries,\
    headline, StopWatch, stop, stoptrace
from pracmln.utils.config import PRACMLNConfig, query_config_pattern, \
    query_mln_filemask, emln_filemask, query_db_filemask, \
    global_config_filename
from pracmln.mln.base import parse_mln, MLN
from pracmln.mln.database import parse_db, Database
from tabulate import tabulate
from cProfile import Profile
import pstats
import StringIO
import pracmln


logger = praclog.logger(__name__)

GUI_SETTINGS = ['window_loc', 'db', 'method', 'use_emln', 'save', 'output_filename', 'grammar', 'queries', 'emln']
ALLOWED_EXTENSIONS = [('PRACMLN project files', '.pracmln'), ('MLN files', '.mln'), ('MLN extension files', '.emln'), ('Database files', '.db')]
DEFAULTNAME = 'unknown{}'
PRACMLN_HOME = os.getenv('PRACMLN_HOME', os.getcwd())
DEFAULT_CONFIG = os.path.join(PRACMLN_HOME, global_config_filename)
WINDOWTITLE = 'PRACMLN Query Tool - {}' + os.path.sep + '{}'
WINDOWTITLEEDITED = 'PRACMLN Query Tool - {}' + os.path.sep + '*{}'


class MLNQuery(object):
    
    def __init__(self, config=None, **params):
        self.configfile = None
        if config is None:
            self._config = {}
        elif isinstance(config, PRACMLNConfig):
            self._config = config.config
            self.configfile = config
        self._config.update(params)

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
        return InferenceMethods.clazz(self._config.get('method', 'MC-SAT'))
        
        
    @property
    def queries(self):
        q = self._config.get('queries', pracmln.ALL)
        if isinstance(q, basestring):
            return parse_queries(self.mln, q)
        return q
    
    
    @property
    def emln(self):
        return self._config.get('emln', None) 
    

    @property
    def cw(self):
        return self._config.get('cw', False)
    
    
    @property
    def cw_preds(self):
        return map(str.strip, self._config.get('cw_preds', '').split(','))
    
    
    @property
    def use_emln(self):
        return self._config.get('use_emln', False)


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
    def save(self):
        return self._config.get('save', False)


    def run(self):
        watch = StopWatch()
        watch.tag('inference', self.verbose)
        # load the MLN
        if isinstance(self.mln, MLN):
            mln = self.mln
        else:
            raise Exception('No MLN specified')
        
        if self.use_emln and self.emln is not None:
            mlnstr = StringIO.StringIO()
            mln.write(mlnstr)
            mlnstr.close()
            mlnstr = str(mlnstr)
            emln = self.emln
            mln = parse_mln(mlnstr + emln, grammar=self.grammar, logic=self.logic)
        
        # load the database
        if isinstance(self.db, Database): 
            db = self.db
        elif isinstance(self.db, list) and len(self.db) == 1:
            db = self.db[0]
        elif isinstance(self.db, list):
            raise Exception('Got {} dbs. Can only handle one for inference.'.format(len(self.db)))
        else:
            raise Exception('DB of invalid format {}'.format(type(self.db)))

        # expand the
        #  parameters
        params = dict(self._config)
        if 'params' in params:
            params.update(eval("dict(%s)" % params['params']))
            del params['params']
        if self.verbose:
            print tabulate(sorted(list(params.viewitems()), key=lambda (k,v): str(k)), headers=('Parameter:', 'Value:'))
        # create the MLN and evidence database and the parse the queries
#         mln = parse_mln(modelstr, searchPath=self.dir.get(), logic=self.config['logic'], grammar=self.config['grammar'])
#         db = parse_db(mln, db_content, ignore_unknown_preds=params.get('ignore_unknown_preds', False))
        if type(db) is list and len(db) > 1:
            raise Exception('Inference can only handle one database at a time')
        elif type(db) is list:
            db = db[0]
        # parse non-atomic params
#         if type(self.queries) is not list:
#             queries = parse_queries(mln, str(self.queries))
        params['cw_preds'] = filter(lambda x: bool(x), self.cw_preds)
        # extract and remove all non-algorithm
        for s in GUI_SETTINGS:
            if s in params: del params[s]
        
        if self.profile:
            prof = Profile()
            print 'starting profiler...'
            prof.enable()
        # set the debug level
        olddebug = praclog.level()
        praclog.level(eval('logging.%s' % params.get('debug', 'WARNING').upper()))
        result = None
        try:
            mln_ = mln.materialize(db)
            mrf = mln_.ground(db)
            inference = self.method(mrf, self.queries, **params)
            if self.verbose:
                print
                print headline('EVIDENCE VARIABLES')
                print
                mrf.print_evidence_vars()

            result = inference.run()
            if self.verbose:
                print
                print headline('INFERENCE RESULTS')
                print
                inference.write()
            if self.verbose:
                print
                inference.write_elapsed_time()
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
        if self.verbose:
            print
            watch.finish()
            watch.printSteps()
        return result


class MLNQueryGUI(object):

    def __init__(self, master, gconf, directory=None):
        self.master = master
        # icon = Tkinter.Image("photo", file=os.path.join(PRACMLN_HOME, 'doc', '_static', 'favicon.ico'))
        # self.master.tk.call('wm', 'iconphoto', self.master._w, icon)

        self.initialized = False

        self.master.bind('<Return>', self.infer)
        self.master.bind('<Escape>', lambda a: self.master.quit())
        self.master.protocol('WM_DELETE_WINDOW', self.quit)

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
        self.btn_saveproj = Button(project_container, text='Save Project...', command=self.noask_save_project)
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

        self.btn_savemln = Button(mln_container, text='Save', command=self.save_mln)
        self.btn_savemln.grid(row=0, column=6, sticky="E")

        # mln editor
        row += 1
        self.mln_editor = SyntaxHighlightingText(self.frame, change_hook=self.onchange_mlncontent)
        self.mln_editor.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # option: use model extension
        row += 1
        self.use_emln = IntVar()
        self.cb_use_emln = Checkbutton(self.frame, text="use model extension", variable=self.use_emln, command=self.onchange_use_emln)
        self.cb_use_emln.grid(row=row, column=1, sticky="W")

        # mln extension selection
        row += 1
        self.emlncontainerrow = row
        self.emln_label = Label(self.frame, text="EMLN: ")
        self.emln_label.grid(row=row, column=0, sticky='E')
        self.emln_container = Frame(self.frame)
        self.emln_container.grid(row=row, column=1, sticky="NEWS")
        self.emln_container.columnconfigure(1, weight=2)

        self.selected_emln = StringVar(master)
        emlnfiles = []
        self.emln_buffer = {}
        self._dirty_emln_name = ''
        self._emln_editor_dirty = False
        self.emln_reload = True
        if len(emlnfiles) == 0: emlnfiles.append("")
        self.list_emlns = apply(OptionMenu, (self.emln_container, self.selected_emln) + tuple(emlnfiles))
        self.list_emlns.grid(row=0, column=1, sticky="NWE")
        self.selected_emln.trace("w", self.select_emln)

        # new emln file
        self.btn_newemln = Button(self.emln_container, text='New', command=self.new_emln)
        self.btn_newemln.grid(row=0, column=2, sticky="W")

        # import emln file
        self.btn_importemln = Button(self.emln_container, text='Import', command=self.import_emln)
        self.btn_importemln.grid(row=0, column=3, sticky="W")

        # delete emln file
        self.btn_delemln = Button(self.emln_container, text='Delete', command=self.delete_emln)
        self.btn_delemln.grid(row=0, column=4, sticky="W")

        # emln filename field & save button
        self.emln_filename = StringVar(master, value='filename.emln')
        self.save_edit_emln = Entry(self.emln_container, textvariable=self.emln_filename)
        self.save_edit_emln.grid(row=0, column=5, sticky="WE")

        self.btn_saveemln = Button(self.emln_container, text='Save', command=self.save_emln)
        self.btn_saveemln.grid(row=0, column=6, sticky="E")

        # emln editor
        row += 1
        self.emln_editor = SyntaxHighlightingText(self.frame)
        self.emln_editor.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)
        self.onchange_use_emln(dirty=False)

        # db selection
        row += 1
        Label(self.frame, text="Evidence: ").grid(row=row, column=0, sticky='E')
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

        self.btn_savedb = Button(db_container, text='Save', command=self.save_db)
        self.btn_savedb.grid(row=0, column=6, sticky="E")

        # db editor
        row += 1
        self.db_editor = SyntaxHighlightingText(self.frame, change_hook=self.onchange_dbcontent)
        self.db_editor.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # inference method selection
        row += 1
        self.list_methods_row = row
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        self.selected_method.trace('w', self.select_method)
        methodnames = sorted(InferenceMethods.names())
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methodnames))
        self.list_methods.grid(row=self.list_methods_row, column=1, sticky="NWE")

        # options
        row += 1
        option_container = Frame(self.frame)
        option_container.grid(row=row, column=1, sticky="NEWS")

        # Multiprocessing
        self.multicore = IntVar()
        self.cb_multicore = Checkbutton(option_container, text="Use all CPUs", variable=self.multicore, command=self.settings_setdirty)
        self.cb_multicore.grid(row=0, column=2, sticky=W)

        # profiling
        self.profile = IntVar()
        self.cb_profile = Checkbutton(option_container, text='Use Profiler', variable=self.profile, command=self.settings_setdirty)
        self.cb_profile.grid(row=0, column=3, sticky=W)

        # verbose
        self.verbose = IntVar()
        self.cb_verbose = Checkbutton(option_container, text='verbose', variable=self.verbose, command=self.settings_setdirty)
        self.cb_verbose.grid(row=0, column=4, sticky=W)

        # options
        self.ignore_unknown_preds = IntVar(master)
        self.cb_ignore_unknown_preds = Checkbutton(option_container, text='ignore unkown predicates', variable=self.ignore_unknown_preds, command=self.settings_setdirty)
        self.cb_ignore_unknown_preds.grid(row=0, column=5, sticky="W")

        # queries
        row += 1
        Label(self.frame, text="Queries: ").grid(row=row, column=0, sticky=E)
        self.query = StringVar(master)
        self.query.trace('w', self.settings_setdirty)
        Entry(self.frame, textvariable = self.query).grid(row=row, column=1, sticky="NEW")

        # additional parameters
        row += 1
        Label(self.frame, text="Add. params: ").grid(row=row, column=0, sticky="NE")
        self.params = StringVar(master)
        self.params.trace('w', self.settings_setdirty)
        self.entry_params = Entry(self.frame, textvariable = self.params)
        self.entry_params.grid(row=row, column=1, sticky="NEW")

        # closed-world predicates
        row += 1
        Label(self.frame, text="CW preds: ").grid(row=row, column=0, sticky="E")

        cw_container = Frame(self.frame)
        cw_container.grid(row=row, column=1, sticky='NEWS')
        cw_container.columnconfigure(0, weight=1)

        self.cwPreds = StringVar(master)
        self.cwPreds.trace('w', self.settings_setdirty)
        self.entry_cw = Entry(cw_container, textvariable = self.cwPreds)
        self.entry_cw.grid(row=0, column=0, sticky="NEWS")

        self.closed_world = IntVar()
        self.cb_closed_world = Checkbutton(cw_container, text="CW Assumption", variable=self.closed_world, command=self.onchange_cw)
        self.cb_closed_world.grid(row=0, column=1, sticky='W')

        # output filename
        row += 1
        output_cont = Frame(self.frame)
        output_cont.grid(row=row, column=1, sticky='NEWS')
        output_cont.columnconfigure(0, weight=1)

        # - filename
        Label(self.frame, text="Output: ").grid(row=row, column=0, sticky="NE")
        self.output_filename = StringVar(master)
        self.entry_output_filename = Entry(output_cont, textvariable=self.output_filename)
        self.entry_output_filename.grid(row=0, column=0, sticky="NEW")

        # - save option
        self.save = IntVar()
        self.cb_save = Checkbutton(output_cont, text="save", variable=self.save)
        self.cb_save.grid(row=0, column=1, sticky=W)

        # start button
        row += 1
        start_button = Button(self.frame, text=">> Start Inference <<", command=self.infer)
        start_button.grid(row=row, column=1, sticky="NEW")

        self.settings_dirty = IntVar()
        self.project_dirty = IntVar()

        self.gconf = gconf
        self.project = None
        self.dir = os.path.abspath(ifNone(gconf['prev_query_path'], DEFAULT_CONFIG))
        self.project_dir = os.path.abspath(ifNone(gconf['prev_query_path'], DEFAULT_CONFIG))
        if gconf['prev_query_project': self.project_dir] is not None:
            self.load_project(os.path.join(self.project_dir, gconf['prev_query_project': self.project_dir]))
        else:
            self.new_project()
        self.config = self.project.queryconf
        self.project.addlistener(self.project_setdirty)

        self.master.geometry(gconf['window_loc_query'])

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
            self.write_config()
            self.master.destroy()


    ####################### PROJECT FUNCTIONS #################################
    def new_project(self):
        self.project = MLNProject()
        self.project.addlistener(self.project_setdirty)
        self.project.name = DEFAULTNAME.format('.pracmln')
        self.reset_gui()
        self.set_config(self.project.queryconf)
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
            self.set_config(self.project.queryconf.config)
            self.update_mln_choices()
            self.update_db_choices()
            if len(self.project.mlns) > 0:
                self.selected_mln.set(self.project.queryconf['mln'] or self.project.mlns.keys()[0])
            if len(self.project.dbs) > 0:
                self.selected_db.set(self.project.queryconf['db'] or self.project.dbs.keys()[0])
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


    ####################### EMLN FUNCTIONS #####################################
    def new_emln(self):
        self.project.add_emln(DEFAULTNAME.format('.emln'), content='')
        self.update_emln_choices()
        self.selected_emln.set(DEFAULTNAME.format('.emln'))


    def import_emln(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('MLN extension files', '.emln')], defaultextension=".emln")
        if filename:
            fpath, fname = ntpath.split(filename)
            self.dir = os.path.abspath(fpath)
            content = mlnpath(filename).content
            self.project.add_emln(fname, content)
            self.update_emln_choices()
            self.selected_emln.set(fname)


    def delete_emln(self):
        fname = self.selected_emln.get().strip()
        fnamestr = fname.strip('*')

        # remove element from project emlns and buffer
        if fname in self.emln_buffer:
            del self.emln_buffer[fname]
        if fname in self.project.emlns:
            self.project.rm_emln(fname)
        if fnamestr in self.project.emlns:
            self.project.rm_emln(fnamestr)
        self.update_emln_choices()

        # select first element from remaining list
        if len(self.project.emlns) > 0:
            self.selected_emln.set(self.project.emlns.keys()[0])
        else:
            self.selected_emln.set('')
            self.emln_editor.delete("1.0", END)
            self.emln_filename.set('')
            self.list_emlns['menu'].delete(0, 'end')


    def save_all_emlns(self):
        current = self.selected_emln.get().strip()
        for emln in self.emln_buffer:
            emlnstr = emln.strip('*')
            content = self.emln_buffer[emln]
            if emln == current:
                content = self.emln_editor.get("1.0", END).strip()
                out(content)
            if emlnstr in self.project.emlns:
                self.project.rm_emln(emlnstr)
            self.project.add_emln(emlnstr, content)

        # reset buffer, dirty flag for editor and update emln selections
        self.emln_buffer.clear()
        self._emln_editor_dirty = False
        self.update_emln_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        self.project_setdirty(False)


    def update_emln(self):
        oldfname = self.selected_emln.get().strip()
        newfname = self.emln_filename.get().strip()
        content = self.emln_editor.get("1.0", END).strip()

        if oldfname:
            if oldfname in self.emln_buffer:
                del self.emln_buffer[oldfname]
            if oldfname == newfname:
                self.project.emlns[oldfname] = content
            else:
                if oldfname in self.project.emlns:
                    self.project.rm_emln(oldfname)
                if newfname != '':
                    self.project.add_emln(newfname, content)

        # reset dirty flag for editor and update emln selections
        self._emln_editor_dirty = False
        self.update_emln_choices()

        self.project.save(dirpath=self.project_dir)
        self.write_gconfig()
        if newfname != '': self.selected_emln.set(newfname)
        self.project_setdirty(False)


    def select_emln(self, *args):
        emlnname = self.selected_emln.get().strip()
        self.project_setdirty(True)

        if emlnname is not None and emlnname != '':
            # filename is neither None nor empty
            if self._emln_editor_dirty:
                # save current state to buffer before updating editor
                self.emln_buffer[self._dirty_emln_name] = self.emln_editor.get("1.0", END).strip()
                self._emln_editor_dirty = True if '*' in emlnname else False
                if not self.emln_reload:
                    self.emln_reload = True
                    return
            if '*' in emlnname:# is edited
                # load previously edited content from buffer instead of emln file in project
                content = self.emln_buffer.get(emlnname, '').strip()
                self.emln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.emln_editor.insert(INSERT, content)
                self.emln_filename.set(emlnname.lstrip('*'))
                self.set_outputfilename()
                self._emln_editor_dirty = True
                self._dirty_emln_name = '*' + emlnname if '*' not in emlnname else emlnname
                return
            if emlnname in self.project.emlns:
                # load content from emln file in project
                content = self.project.emlns.get(emlnname, '').strip()
                self.emln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.emln_editor.insert(INSERT, content)
                self.emln_filename.set(emlnname)
                self.set_outputfilename()
                self._emln_editor_dirty = False
        else:
            # should not happen
            self.emln_editor.delete("1.0", END)
            self.emln_filename.set('')
            self.list_emlns['menu'].delete(0, 'end')


    def update_emln_choices(self):
        self.list_emlns['menu'].delete(0, 'end')

        new_emlns = sorted([i for i in self.project.emlns.keys() if '*'+i not in self.emln_buffer] + self.emln_buffer.keys())
        for emln in new_emlns:
            self.list_emlns['menu'].add_command(label=emln, command=_setit(self.selected_emln, emln))


    def onchange_emlncontent(self, *args):
        if not self._emln_editor_dirty:
            self._emln_editor_dirty = True
            self.emln_reload = False
            fname = self.selected_emln.get().strip()
            fname = '*' + fname if '*' not in fname else fname
            self._dirty_emln_name = fname
            self.emln_buffer[self._dirty_emln_name] = self.emln_editor.get("1.0", END).strip()
            self.update_emln_choices()
            self.selected_emln.set(self._dirty_emln_name)


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

    def select_method(self, *args):
        self.set_outputfilename()
        self.settings_setdirty()


    def onchange_use_emln(self, dirty=True, *args):
        if not self.use_emln.get():
            self.emln_label.grid_forget()
            self.emln_container.grid_forget()
            self.emln_editor.grid_forget()
        else:
            self.emln_label.grid(row=self.emlncontainerrow, column=0, sticky="NWES")
            self.emln_container.grid(row=self.emlncontainerrow, column=1, sticky="NWES")
            self.emln_editor.grid(row=self.emlncontainerrow+1, column=1, sticky="NWES")
        if dirty:
            self.settings_setdirty()


    def select_logic(self, *args):
        self.logic = self.selected_logic.get()
        self.settings_setdirty()


    def onchange_cw(self, *args):
        if self.closed_world.get():
            self.entry_cw.configure(state=DISABLED)
        else:
            self.entry_cw.configure(state=NORMAL)
        self.settings_setdirty()


    def select_grammar(self, *args):
        self.grammar = self.selected_grammar.get()
        self.settings_setdirty()


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
        self.selected_emln.set(ifNone(conf.get('emln'), ""))
        self.selected_db.set(ifNone(conf.get('db'), ""))
        self.selected_method.set(ifNone(conf.get("method"), InferenceMethods.name('MCSAT'), transform=InferenceMethods.name))
        self.multicore.set(ifNone(conf.get('multicore'), 0))
        self.profile.set(ifNone(conf.get('profile'), 0))
        self.params.set(ifNone(conf.get('params'), ''))
        self.use_emln.set(ifNone(conf.get('use_emln'), 0))
        self.verbose.set(ifNone(conf.get('verbose'), 1))
        self.ignore_unknown_preds.set(ifNone(conf.get('ignore_unknown_preds'), 0))
        self.output_filename.set(ifNone(conf.get('output_filename'), ''))
        self.cwPreds.set(ifNone(conf.get('cw_preds'), ''))
        self.closed_world.set(ifNone(conf.get('cw'), 0))
        self.save.set(ifNone(conf.get('save'), 0))
        self.query.set(ifNone(conf.get('queries'), ''))
        self.onchange_cw()


    def set_outputfilename(self):
        if not hasattr(self, "output_filename") or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        mln = self.mln_filename.get()
        db = self.db_filename.get()
        if "" in (mln, db): return
        if self.selected_method.get():
            method = InferenceMethods.clazz(self.selected_method.get())
            methodid = InferenceMethods.id(method)
            filename = config.query_output_filename(mln, methodid, db)
            self.output_filename.set(filename)


    def update_settings(self):
        out('update_settings')

        self.config = PRACMLNConfig()
        self.config["db"] = self.selected_db.get().strip().lstrip('*')
        self.config['mln'] = self.selected_mln.get().strip().lstrip('*')
        self.config["method"] = InferenceMethods.id(self.selected_method.get().strip())
        self.config["params"] = self.params.get().strip()
        self.config["queries"] = self.query.get()
        self.config['emln'] = self.selected_emln.get().strip().lstrip('*')
        self.config["output_filename"] = self.output_filename.get().strip()
        self.config["cw"] = self.closed_world.get()
        self.config["cw_preds"] = self.cwPreds.get()
        self.config['profile'] = self.profile.get()
        self.config["use_emln"] = self.use_emln.get()
        self.config['logic'] = self.selected_logic.get()
        self.config['grammar'] = self.selected_grammar.get()
        self.config['multicore'] = self.multicore.get()
        self.config['save'] = self.save.get()
        self.config['ignore_unknown_preds'] = self.ignore_unknown_preds.get()
        self.config['verbose'] = self.verbose.get()
        self.config['window_loc'] = self.master.winfo_geometry()
        self.config['dir'] = self.dir
        self.project.queryconf = PRACMLNConfig()
        self.project.queryconf.update(self.config.config.copy())
        self.save_mln()
        self.save_emln()
        self.save_db()


    def write_gconfig(self, savegeometry=True):
        self.gconf['prev_query_path'] = self.dir
        self.gconf['prev_query_project': self.dir] = self.project.name

        # save geometry
        if savegeometry:
            self.gconf['window_loc_query'] = self.master.geometry()
        self.gconf.dump()


    def infer(self, savegeometry=True, options={}, *args):
        mln_content = self.mln_editor.get("1.0", END).encode('utf8').strip()
        db_content = self.db_editor.get("1.0", END).encode('utf8').strip()

        # create conf from current gui settings
        self.update_settings()

        # write gui settings
        self.write_gconfig(savegeometry=savegeometry)

        # hide gui
        self.master.withdraw()

        try:
            print headline('PRACMLN QUERY TOOL')
            print

            if options.get('mlnarg') is not None:
                mlnobj = MLN(mlnfile=os.path.abspath(options.get('mlnarg')), logic=self.config.get('logic', 'FirstOrderLogic'), grammar=self.config.get('grammar', 'PRACGrammar'))
            else:
                mlnobj = parse_mln(mln_content, searchpaths=[self.dir], projectpath=os.path.join(self.dir, self.project.name), logic=self.config.get('logic', 'FirstOrderLogic'), grammar=self.config.get('grammar', 'PRACGrammar'))

            if options.get('emlnarg') is not None:
                emln_content = mlnpath(options.get('emlnarg')).content
            else:
                emln_content = self.emln_editor.get("1.0", END).encode('utf8').strip()

            if options.get('dbarg') is not None:
                dbobj = Database.load(mlnobj, dbfile=options.get('dbarg'), ignore_unknown_preds=self.config.get('ignore_unknown_preds', True))
            else:
                out(self.config.get('ignore_unknown_preds', True))
                dbobj = parse_db(mlnobj, db_content, ignore_unknown_preds=self.config.get('ignore_unknown_preds', True))

            if options.get('queryarg') is not None:
                self.config["queries"] = options.get('queryarg')

            infer = MLNQuery(config=self.config, mln=mlnobj, db=dbobj, emln=emln_content)
            result = infer.run()


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
                fname = self.output_filename.get()
                self.project.add_result(fname, output.getvalue())
                self.project.save(dirpath=self.dir)
                logger.info('saved result to file results/{} in project {}'.format(fname, self.project.name))
            else:
                logger.debug('No output file given - results have not been saved.')

        except:
            traceback.print_exc()

        # restore main window
        sys.stdout.flush()
        self.master.deiconify()


# -- main app --
if __name__ == '__main__':
    praclog.level(praclog.DEBUG)

    # read command-line options
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-i", "--mln", dest="mlnarg", help="the MLN model file to use")
    parser.add_option("-x", "--emln", dest="emlnarg", help="the MLN model extension file to use")
    parser.add_option("-q", "--queries", dest="queryarg", help="queries (comma-separated)")
    parser.add_option("-e", "--evidence", dest="dbarg", help="the evidence database file")
    parser.add_option("-r", "--results-file", dest="outputfile", help="the results file to save")
    parser.add_option("--run", action="store_true", dest="run", default=False, help="run with last settings (without showing GUI)")
    parser.add_option("--noPMW", action="store_true", dest="nopmw", default=False, help="do not use Python mega widgets even if available")
    (opts, args) = parser.parse_args()
    options = vars(opts)

    # create gui
    if opts.nopmw:
        widgets.havePMW = False

    root = Tk()
    conf = PRACMLNConfig(DEFAULT_CONFIG)
    app = MLNQueryGUI(root, conf, directory=args[0] if args else None)

    if opts.run:
        logger.debug('running mlnlearn without gui')
        app.infer(savegeometry=False, options=options)
    else:
        root.mainloop()

