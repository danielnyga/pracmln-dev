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
from tkFileDialog import askdirectory, askopenfile, askopenfilename, \
    asksaveasfilename
import os
import ntpath
import re
import tkMessageBox
import traceback
from pracmln.utils.project import MLNProject
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
    query_mln_filemask, emln_filemask, query_db_filemask
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
DEFAULTNAME = 'unnamed{}'

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
        elif isinstance(self.mln, basestring):
            raise Exception('WAAAAAAAAAH! MLN IS STRING')
            # mlnfile = os.path.join(self.directory, self.mln)
            # mln = MLN(mlnfile=mlnfile, logic=self.logic, grammar=self.grammar)
        else:
            raise Exception('No MLN specified')
        
        if self.use_emln and self.emln is not None:
            mlnstr = StringIO()
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
        self.initialized = False
        
        master.title("PRACMLN Query Tool")
        self.project = MLNProject()
        self.gconf = gconf
        self.config = self.project.queryconf
        self.master = master
        self.master.bind('<Return>', self.start)
        self.master.bind('<Escape>', lambda a: self.master.quit())
        self.master.protocol('WM_DELETE_WINDOW', self.quit)
        
        self.frame = Frame(master)
        self.frame.pack(fill=BOTH, expand=1)
        self.frame.columnconfigure(1, weight=1)

        row = 0
        # pracmln project options
        Label(self.frame, text='PRACMLN Project: ').grid(row=row, column=0, sticky='E')
        project_container = Frame(self.frame)
        project_container.grid(row=row, column=1, sticky="NEWS")

        # new proj file
        self.btn_newproj = Button(project_container, text='New Project...', command=self.new_project)
        self.btn_newproj.grid(row=0, column=1, sticky="W")

        # open proj file
        self.btn_openproj = Button(project_container, text='Open Project...', command=self.load_project)
        self.btn_openproj.grid(row=0, column=2, sticky="W")

        # save proj file
        self.btn_saveproj = Button(project_container, text='Save Project...', command=self.save_project)
        self.btn_saveproj.grid(row=0, column=3, sticky="W")

        # grammar selection
        row += 1
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

        # mln selection
        row += 1
        Label(self.frame, text="MLN: ").grid(row=row, column=0, sticky='E')
        mln_container = Frame(self.frame)
        mln_container.grid(row=row, column=1, sticky="NEWS")

        self.selected_mln = StringVar(master)
        mlnfiles = sorted(self.project.mlns.keys())
        if len(mlnfiles) == 0: mlnfiles.append("(no %s files found)" % str(query_mln_filemask))
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
        self.mln_editor = SyntaxHighlightingText(self.frame)
        self.mln_editor.grid(row=row, column=1, sticky="NWES")

        # option: use model extension
        row += 1
        self.use_emln = IntVar()
        self.cb_use_emln = Checkbutton(self.frame, text="use model extension", variable=self.use_emln)
        self.cb_use_emln.grid(row=row, column=1, sticky="W")
        self.use_emln.trace("w", self.onchange_use_emln)
        
        # mln extension selection
        row += 1
        self.emlncontainerrow = row
        self.emln_label = Label(self.frame, text="EMLN: ")
        self.emln_label.grid(row=row, column=0, sticky='E')
        self.emln_container = Frame(self.frame)
        self.emln_container.grid(row=row, column=1, sticky="NEWS")

        self.selected_emln = StringVar(master)
        emlnfiles = sorted(self.project.emlns.keys())
        if len(emlnfiles) == 0: emlnfiles.append("(no %s files found)" % str(config.emln_filemask))
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
        self.onchange_use_emln()

        # db selection
        row += 1
        Label(self.frame, text="Evidence: ").grid(row=row, column=0, sticky='E')
        db_container = Frame(self.frame)
        db_container.grid(row=row, column=1, sticky="NEWS")

        self.selected_db = StringVar(master)
        dbfiles = sorted(self.project.dbs.keys())
        if len(dbfiles) == 0: dbfiles.append("(no %s files found)" % str(config.query_db_filemask))
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
        self.db_editor = SyntaxHighlightingText(self.frame)
        self.db_editor.grid(row=row, column=1, sticky="NWES")
        self.onchange_use_emln()

        # inference method selection
        row += 1
        self.list_methods_row = row
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        methodnames = sorted(InferenceMethods.names())
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methodnames))
        self.list_methods.grid(row=self.list_methods_row, column=1, sticky="NWE")

        # options
        row += 1
        option_container = Frame(self.frame)
        option_container.grid(row=row, column=1, sticky="NEWS")

        # Multiprocessing
        self.multicore = IntVar()
        self.cb_multicore = Checkbutton(option_container, text="Use all CPUs", variable=self.multicore)
        self.cb_multicore.grid(row=0, column=2, sticky=W)

        # profiling
        self.profile = IntVar()
        self.cb_profile = Checkbutton(option_container, text='Use Profiler', variable=self.profile)
        self.cb_profile.grid(row=0, column=3, sticky=W)

        # verbose
        self.verbose = IntVar()
        self.cb_verbose = Checkbutton(option_container, text='verbose', variable=self.verbose)
        self.cb_verbose.grid(row=0, column=4, sticky=W)

        # options
        self.ignore_unknown_preds = IntVar(master)
        self.cb_ignore_unknown_preds = Checkbutton(option_container, text='ignore unkown predicates', variable=self.ignore_unknown_preds)
        self.cb_ignore_unknown_preds.grid(row=0, column=5, sticky="W")

        # queries
        row += 1
        Label(self.frame, text="Queries: ").grid(row=row, column=0, sticky=E)
        self.query = StringVar(master)
        Entry(self.frame, textvariable = self.query).grid(row=row, column=1, sticky="NEW")

        # additional parameters
        row += 1
        Label(self.frame, text="Add. params: ").grid(row=row, column=0, sticky="NE")
        self.params = StringVar(master)
        self.entry_params = Entry(self.frame, textvariable = self.params)
        self.entry_params.grid(row=row, column=1, sticky="NEW")

        # closed-world predicates
        row += 1
        Label(self.frame, text="CW preds: ").grid(row=row, column=0, sticky="E")
        
        cw_container = Frame(self.frame)
        cw_container.grid(row=row, column=1, sticky='NEWS')
        cw_container.columnconfigure(0, weight=1)
        
        self.cwPreds = StringVar(master)
        self.entry_cw = Entry(cw_container, textvariable = self.cwPreds)
        self.entry_cw.grid(row=0, column=0, sticky="NEWS")
        
        self.closed_world = IntVar()
        self.closed_world.trace('w', self.onChangeClosedWorld)
        self.cb_closed_world = Checkbutton(cw_container, text="CW Assumption", variable=self.closed_world)
        self.cb_closed_world.grid(row=0, column=1, sticky='W')


        # output filename
        row += 1
        Label(self.frame, text="Output: ").grid(row=row, column=0, sticky="NE")
        frame = Frame(self.frame)
        frame.grid(row=row, column=1, sticky="NEW")
        frame.columnconfigure(0, weight=1)
        # - filename
        self.output_filename = StringVar(master)
        self.entry_output_filename = Entry(frame, textvariable = self.output_filename)
        self.entry_output_filename.grid(row=0, column=0, sticky="NEW")
        # - save option
        self.save_results = IntVar()
        self.cb_save_results = Checkbutton(frame, text="save", variable=self.save_results)
        self.cb_save_results.grid(row=0, column=1, sticky=W)

        # start button
        row += 1
        start_button = Button(self.frame, text=">> Start Inference <<", command=self.start)
        start_button.grid(row=row, column=1, sticky="NEW")

        self.set_dir(ifNone(directory, ifNone(gconf['prev_query_path'], os.getcwd())))
#         if gconf['prev_query_mln':self.dir.get()] is not None:
#             self.selected_mln.set(gconf['prev_query_mln':self.dir.get()])
        
        self.master.geometry(gconf['window_loc_query'])
        self.initialized = True


    def quit(self):
        if self.project.dirty:
            if tkMessageBox.askokcancel("Save changes", "You have unsaved project changes. Do you want to save them before quitting?"):
                self.project.save()
        self.master.destroy()


    ####################### PROJECT FUNCTIONS #################################
    def new_project(self):
        self.project = MLNProject()
        self.set_config(self.project.queryconf)
        self.update_mln_choices()
        self.update_emln_choices()
        self.update_db_choices()


    def load_project(self):
        filename = askopenfilename(initialdir='.', filetypes=[('PRACMLN project files', '.pracmln')], defaultextension=".pracmln")
        self.dir, _ = ntpath.split(filename)
        if filename:
            proj = MLNProject.open(filename)
            self.project = proj
            self.set_config(self.project.queryconf.config)
            self.update_mln_choices()
            self.update_emln_choices()
            self.update_db_choices()
            self.selected_mln.set(self.project.queryconf['mln'])
            self.selected_emln.set(self.project.queryconf['emln'])
            self.selected_db.set(self.project.queryconf['db'])


    def save_project(self):
        fullfilename = asksaveasfilename(confirmoverwrite=True)
        if fullfilename:
            fpath, fname = ntpath.split(fullfilename)
            fname = fname.split('.')[0]
            self.project.name = fname
            self.update_settings()
            self.project.write()
            self.project.save(fpath)


    ####################### MLN FUNCTIONS #####################################
    def new_mln(self):
        self.mln_filename.set(DEFAULTNAME.format('.mln'))
        self.project.add_mln(DEFAULTNAME.format(''), '')
        self.update_mln_choices()
        self.selected_mln.set(DEFAULTNAME.format('.mln'))


    def import_mln(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('MLN files', '.mln')], defaultextension=".mln")
        fpath, fname = ntpath.split(filename)
        content = self.import_file(filename)
        self.project.add_mln(fname, content)
        self.update_mln_choices()
        self.selected_mln.set(fname)


    def delete_mln(self):
        self.project.rm_mln(self.selected_mln.get())
        self.update_mln_choices()

    def save_mln(self):
        oldfname = self.selected_mln.get()
        newfname = self.mln_filename.get()
        content = self.mln_editor.get("1.0", END).encode('utf-8')
        self.project.rm_mln(oldfname)
        self.project.add_mln(newfname, content)
        self.update_mln_choices()
        self.selected_mln.set(newfname)


    def select_mln(self, *args):
        mlnname = self.selected_mln.get()
        if mlnname:
            content = self.project.mlns.get(mlnname, '<<empty>>')
            if content:
                self.mln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.mln_editor.insert(INSERT, content)
        self.mln_filename.set(mlnname)


    def update_mln_choices(self):
        self.selected_mln.set('')
        self.list_mlns['menu'].delete(0, 'end')

        new_mlns = sorted(self.project.mlns.keys())
        for mln in new_mlns:
            self.list_mlns['menu'].add_command(label=mln, command=_setit(self.selected_mln, mln))


    ####################### EMLN FUNCTIONS ####################################
    def new_emln(self):
        self.emln_filename.set(DEFAULTNAME.format('.emln'))
        self.project.add_emln(DEFAULTNAME.format(''), '')
        self.update_emln_choices()
        self.selected_emln.set(DEFAULTNAME.format('.emln'))


    def import_emln(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('MLN extension files', '.emln')], defaultextension=".emln")
        fpath, fname = ntpath.split(filename)
        content = self.import_file(filename)
        self.project.add_emln(fname, content)
        self.update_emln_choices()
        self.selected_emln.set(fname)


    def delete_emln(self):
        self.project.rm_emln(self.selected_emln.get())
        self.update_emln_choices()


    def save_emln(self):
        oldfname = self.selected_emln.get()
        newfname = self.emln_filename.get()
        content = self.emln_editor.get("1.0", END).encode('utf-8')
        self.project.rm_emln(oldfname)
        self.project.add_emln(newfname, content)
        self.update_emln_choices()
        self.selected_emln.set(newfname)


    def select_emln(self, *args):
        emlnname = self.selected_emln.get()
        if emlnname:
            content = self.project.emlns.get(emlnname, '<<empty>>')
            if content:
                self.emln_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.emln_editor.insert(INSERT, content)
        self.emln_filename.set(emlnname)

    def update_emln_choices(self):
        self.selected_emln.set('')
        self.list_emlns['menu'].delete(0, 'end')

        new_emlns = sorted(self.project.emlns.keys())
        for emln in new_emlns:
            self.list_emlns['menu'].add_command(label=emln, command=_setit(self.selected_emln, emln))


    ####################### DB FUNCTIONS ######################################
    def new_db(self):
        self.db_filename.set(DEFAULTNAME.format('.db'))
        self.project.add_db(DEFAULTNAME.format(''), '')
        self.update_db_choices()
        self.selected_db.set(DEFAULTNAME.format('.db'))


    def import_db(self):
        filename = askopenfilename(initialdir=self.dir, filetypes=[('Database files', '.db')], defaultextension=".db")
        fpath, fname = ntpath.split(filename)
        content = self.import_file(filename)
        self.project.add_db(fname, content)
        self.update_db_choices()
        self.selected_db.set(fname)


    def delete_db(self):
        self.project.rm_db(self.selected_db.get())
        self.update_db_choices()


    def save_db(self):
        oldfname = self.selected_db.get()
        newfname = self.db_filename.get()
        content = self.db_editor.get("1.0", END).encode('utf-8')
        self.project.rm_db(oldfname)
        self.project.add_db(newfname, content)
        self.update_db_choices()
        self.selected_db.set(newfname)


    def select_db(self, *args):
        dbname = self.selected_db.get()
        if dbname:
            content = self.project.dbs.get(dbname, '<<empty>>')
            if content:
                self.db_editor.delete("1.0", END)
                content = content.replace("\r", "")
                self.db_editor.insert(INSERT, content)
        self.db_filename.set(dbname)


    def update_db_choices(self):
        self.selected_db.set('')
        self.list_dbs['menu'].delete(0, 'end')

        new_dbs = sorted(self.project.dbs.keys())
        for db in new_dbs:
            self.list_dbs['menu'].add_command(label=db, command=_setit(self.selected_db, db))


    ####################### GENERAL FUNCTIONS #################################
    def import_file(self, filename):
        if os.path.exists(filename):
            content = file(filename).read()
            content = content.replace("\r", "")
        else:
            content = ""
        return content


    def set_dir(self, dirpath):
        self.dir = os.path.abspath(dirpath)


    def onChangeUseMultiCPU(self, *args):
        pass


    def onchange_use_emln(self, *args):
        if not self.use_emln.get():
            self.emln_label.grid_forget()
            self.emln_container.grid_forget()
            self.emln_editor.grid_forget()
        else:
            self.emln_label.grid(row=self.emlncontainerrow, column=0, sticky="NWES")
            self.emln_container.grid(row=self.emlncontainerrow, column=1, sticky="NWES")
            self.emln_editor.grid(row=self.emlncontainerrow+1, column=1, sticky="NWES")


    def onChangeLogic(self, name = None, index = None, mode = None):
        pass
    
    
    def onChangeClosedWorld(self, name=None, index=None, mode=None):
        if self.closed_world.get():
            self.entry_cw.configure(state=DISABLED)
        else:
            self.entry_cw.configure(state=NORMAL)
        
    
    def onChangeGrammar(self, name=None, index=None, mode=None):
        self.grammar = eval(self.selected_grammar.get())(None)

        
    def set_config(self, conf):
        self.config = conf
        self.selected_grammar.set(ifNone(conf.get('grammar'), 'PRACGrammar'))
        self.selected_logic.set(ifNone(conf.get('logic'), 'FirstOrderLogic'))
        self.selected_mln.set(ifNone(conf.get('mln'), "(no %s files found)" % str(query_mln_filemask)))
        self.selected_emln.set(ifNone(conf.get('emln'), "(no %s files found)" % str(emln_filemask)))
        self.selected_db.set(ifNone(conf.get('db'), "(no %s files found)" % str(query_db_filemask)))
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
        self.save_results.set(ifNone(conf.get('save'), 0))
        self.query.set(ifNone(conf.get('queries'), 'foo, bar'))
        self.onChangeClosedWorld()
        
        
    def setOutputFilename(self):
        if not self.initialized or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        fn = config.query_output_filename(self.mln_filename, self.db_filename)
        self.output_filename.set(fn)


    # returns content of given file, replaces includes by content of the included file
    def get_file_content(self, fcontent, files):
        content = ''
        for l in fcontent:
            if '#include' in l:
                includefile = re.sub('#include ([\w,\s-]+\.[A-Za-z])', '\g<1>', l).strip()
                if includefile in files:
                    content += '{}\n'.format(self.get_file_content(files[includefile].splitlines(), files))
                else:
                    content += '{}\n'.format(l)
            else:
                content += '{}\n'.format(l)
        return content


    def update_settings(self):
        mln = self.selected_mln.get().encode('utf8')
        emln = self.selected_emln.get().encode('utf8')
        db = self.selected_db.get().encode('utf8')
        output = self.output_filename.get().encode('utf8')
        methodname = self.selected_method.get().encode('utf8')
        params = self.params.get().encode('utf8')

        self.config = PRACMLNConfig()
        self.config["db"] = db
        self.config['mln'] = mln
        self.config["method"] = InferenceMethods.id(methodname)
        self.config["params"] = params
        self.config["queries"] = self.query.get()
        self.config['emln'] = emln
        self.config["output_filename"] = output
        self.config["cw"] = self.closed_world.get()
        self.config["cw_preds"] = self.cwPreds.get()
        self.config['profile'] = self.profile.get()
        self.config["use_emln"] = self.use_emln.get()
        self.config['logic'] = self.selected_logic.get()
        self.config['grammar'] = self.selected_grammar.get()
        self.config['multicore'] = self.multicore.get()
        self.config['save'] = self.save_results.get()
        self.config['ignore_unknown_preds'] = self.ignore_unknown_preds.get()
        self.config['verbose'] = self.verbose.get()
        self.project.queryconf = PRACMLNConfig()
        self.project.queryconf.update(self.config.config.copy())
        self.project.mlns[mln] = self.mln_editor.get("1.0", END).encode('utf8')
        self.project.emlns[emln] = self.emln_editor.get("1.0", END).encode('utf8')
        self.project.dbs[db] = self.db_editor.get("1.0", END).encode('utf8')


    def start(self, *args):
        mln_content = self.get_file_content(self.mln_editor.get("1.0", END).encode('utf8').splitlines(), self.project.mlns)
        emln_content = self.get_file_content(self.emln_editor.get("1.0", END).encode('utf8').splitlines(), self.project.emlns)
        db_content = self.get_file_content(self.db_editor.get("1.0", END).encode('utf8').splitlines(), self.project.dbs)

        # update settings
        self.update_settings()
        self.config['window_loc'] = self.master.winfo_geometry()

        # write settings
        logger.debug('writing config...')
        self.gconf['prev_query_path'] = self.dir
        self.gconf['prev_query_mln': self.dir] = self.selected_mln.get()
        self.gconf['window_loc_query'] = self.master.geometry()

        # hide main window
        self.master.withdraw()

        try:
            print headline('PRAC QUERY TOOL')
            print
            mlnobj = parse_mln(mln_content)
            dbobj = parse_db(mlnobj, db_content)
            infer = MLNQuery(config=self.config, mln=mlnobj, db=dbobj, emln=emln_content)
            result = infer.run()
            if self.save_results.get():
                output = StringIO.StringIO()
                result.write(output)
                self.project.add_result(self.output_filename.get(), output.getvalue())
        except:
            traceback.print_exc()

        sys.stdout.flush()
        # restore main window
        self.master.deiconify()


# -- main app --
if __name__ == '__main__':
    praclog.level(praclog.DEBUG)
    
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
    # update settings with command-line information
#     settings.update(dict(filter(lambda x: x[1] is not None, options.__dict__.iteritems())))
#     if len(args) > 1:
#         settings["params"] = (settings.get("params", "") + " ".join(args)).strip()
    # create gui
    if options.noPMW:
        widgets.havePMW = False
    root = Tk()
    
    conf = PRACMLNConfig()
    app = MLNQueryGUI(root, conf, directory=args[0] if args else None)
    if options.run:
        app.start(saveGeometry=False)
    else:
        root.mainloop()

