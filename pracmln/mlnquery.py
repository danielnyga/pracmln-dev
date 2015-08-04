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
from tkFileDialog import askdirectory
import os
import re
import traceback
from utils import widgets
from mln.methods import InferenceMethods
from mln.inference import *
from utils.widgets import FilePickEdit
from logic.grammar import StandardGrammar, PRACGrammar  # @UnusedImport
import logging
from utils import config
from pracmln import praclog
from tkMessageBox import showerror, askyesno
from pracmln.mln.util import out, ifNone, trace, parse_queries,\
    headline, StopWatch
from pracmln.utils.config import PRACMLNConfig, query_config_pattern
from pracmln.mln.base import parse_mln
from pracmln.mln.database import parse_db
from tabulate import tabulate
from cProfile import Profile
import pstats


logger = praclog.logger(__name__)

GUI_SETTINGS = ['window_loc', 'db_rename', 'mln_rename', 'db', 'method', 'use_emln', 'save', 'output_filename', 'grammar', 'queries', 'emln']

class MLNQueryGUI(object):

    def __init__(self, master, gconf, directory=None):
        self.initialized = False
        
        master.title("PRACMLN Query Tool")
        
        self.gconf = gconf
        self.master = master
        
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
        self.selected_mln = FilePickEdit(self.frame, config.query_mln_filemask, '', 22, 
                                         self.select_mln, rename_on_edit='', 
                                         font=config.fixed_width_font, coloring=True)
        self.selected_mln.grid(row=row, column=1, sticky="NWES")
        self.frame.rowconfigure(row, weight=1)

        # option: use model extension
        self.use_emln = IntVar()
        self.cb_use_emln = Checkbutton(self.selected_mln.options_frame, text="use model extension", variable=self.use_emln)
        self.cb_use_emln.pack(side=LEFT)
        self.use_emln.trace("w", self.onChangeUseEMLN)
        
        # mln extension selection
        self.selected_emln = FilePickEdit(self.selected_mln, "*.emln", None, 12, None, rename_on_edit=0, font=config.fixed_width_font, coloring=True)
        self.onChangeUseEMLN()

        # evidence database selection
        row += 1
        Label(self.frame, text="Evidence: ").grid(row=row, column=0, sticky=NE)
        self.selected_db = FilePickEdit(self.frame, config.query_db_filemask, '', 
                                        12, self.changedDB, rename_on_edit=0, 
                                        font=config.fixed_width_font, coloring=True)
        self.selected_db.grid(row=row,column=1, sticky="NWES")
        self.ignore_unknown_preds = IntVar(master)
        self.cb_ignore_unknown_preds = Checkbutton(self.selected_db.options_frame, text='ignore unkown predicates', variable=self.ignore_unknown_preds)
        self.cb_ignore_unknown_preds.pack(side=LEFT)
        self.frame.rowconfigure(row, weight=1)

        # inference method selection
        row += 1
        self.list_methods_row = row
        Label(self.frame, text="Method: ").grid(row=row, column=0, sticky=E)
        self.selected_method = StringVar(master)
        methods = InferenceMethods.getNames()
        self.list_methods = apply(OptionMenu, (self.frame, self.selected_method) + tuple(methods))
        self.list_methods.grid(row=self.list_methods_row, column=1, sticky="NWE")

        # queries
        row += 1
        Label(self.frame, text="Queries: ").grid(row=row, column=0, sticky=E)
        self.query = StringVar(master)
        Entry(self.frame, textvariable = self.query).grid(row=row, column=1, sticky="NEW")
        
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

        # additional parameters
        row += 1
        Label(self.frame, text="Add. params: ").grid(row=row, column=0, sticky="NE")
        self.params = StringVar(master)
        self.entry_params = Entry(self.frame, textvariable = self.params)
        self.entry_params.grid(row=row, column=1, sticky="NEW")

        # closed-world predicates
        row += 1
        Label(self.frame, text="CW preds: ").grid(row=row, column=0, sticky="NEWS")
        
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

        self.set_dir(ifNone(directory, ifNone(conf['prev_query_path'], os.getcwd())))
        if gconf['prev_query_mln':self.dir.get()] is not None:
            self.selected_mln.set(gconf['prev_query_mln':self.dir.get()])
                    
        self.set_window_loc()
        self.initialized = True


    def set_window_loc(self):
        g = self.config["window_loc"]
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
        self.selected_emln.setDirectory(dirpath)
        self.selected_db.setDirectory(dirpath)
        self.dir.set(dirpath)
        

    def select_dir(self):
        dirname = askdirectory()
        logger.info('switching to %s' % dirname)
        if dirname: self.set_dir(dirname)
         

    def select_mln(self, mlnname):
        confname = os.path.join(self.dir.get(), query_config_pattern % mlnname)
        if not self.initialized or os.path.exists(confname) and askyesno('PRACMLN', 'A configuration file was found for the selected MLN.\nDo want to load the configuration?'):
            self.set_config(PRACMLNConfig(confname))
        self.mln_filename = mlnname
        self.setOutputFilename()


    def changedDB(self, name):
        self.db_filename = name
        self.setOutputFilename()

            
    def onChangeUseMultiCPU(self, *args):
        pass


    def onChangeUseEMLN(self, *args):
        if not self.use_emln.get():
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
        
        
    def set_config(self, conf):
        self.config = conf
        self.selected_grammar.set(ifNone(conf['grammar'], 'PRACGrammar'))
        self.selected_logic.set(ifNone(conf['logic'], 'FirstOrderLogic'))
        self.selected_mln.rename_on_edit.set(ifNone(conf['mln_rename'], 0))
        self.selected_db.select(ifNone(conf['db'], ''))
        self.selected_db.rename_on_edit.set(ifNone(conf['db_rename'], False))
        self.selected_method.set(ifNone(conf['method'], 'MC-SAT'))
        self.selected_emln.set(ifNone(conf['emln'], ''))
        self.multicore.set(ifNone(conf['multicore'], False))
        self.profile.set(ifNone(conf['profile'], False))
        self.params.set(ifNone(conf['params'], ''))
        self.use_emln.set(ifNone(conf['use_emln'], False))
        self.verbose.set(ifNone(conf['verbose'], 1))
        self.ignore_unknown_preds.set(ifNone(conf['ignore_unknown_preds'], False))
        if self.use_emln.get():
            self.selected_emln.select(self.use_emln.get())
        self.output_filename.set(ifNone(conf['output_filename'], ''))
        self.cwPreds.set(ifNone(conf['cw_preds'], ''))
        self.closed_world.set(ifNone(conf['cw'], False))
        self.save_results.set(ifNone(conf['save'], False))
        self.query.set(ifNone(conf['queries'], 'foo, bar'))
        self.selected_emln.set(ifNone(conf['use_emln'], False))
        self.onChangeClosedWorld()
        
        
    def setOutputFilename(self):
        if not self.initialized or not hasattr(self, "db_filename") or not hasattr(self, "mln_filename"):
            return
        fn = config.query_output_filename(self.mln_filename, self.db_filename)
        self.output_filename.set(fn)


    def start(self):
        mln = self.selected_mln.get().encode('utf8')
        emln = str(self.selected_emln.get().strip())
        db = str(self.selected_db.get())
        mln_content = self.selected_mln.get_text().strip().encode('utf8')
        db_content = str(self.selected_db.get_text().strip())
        emln_content = str(self.selected_emln.get_text().strip())
        output = str(self.output_filename.get())
        method = str(self.selected_method.get())
        params = str(self.params.get())
        
        # update settings
        self.config = PRACMLNConfig(os.path.join(self.dir.get(), query_config_pattern % mln))
        self.config["mln_rename"] = self.selected_mln.rename_on_edit.get()
        self.config["db"] = db
        self.config["db_rename"] = self.selected_db.rename_on_edit.get()
        self.config["method"] = method
        self.config["params"] = params
        self.config["queries"] = self.query.get()
        self.config['emln'] = self.selected_emln.get()
        self.config["output_filename"] = output
        self.config["cw"] = self.closed_world.get()
        self.config["cw_preds"] = self.cwPreds.get()
        self.config['profile'] = self.profile.get()
        self.config["use_emln"] = self.use_emln.get()
        self.config['logic'] = self.selected_logic.get()
        self.config['grammar'] = self.selected_grammar.get()
        self.config['multicore'] = self.multicore.get()
        self.config['save'] = self.save_results.get()
        self.config["window_loc"] = self.master.winfo_geometry()
        self.config['ignore_unknown_preds'] = self.ignore_unknown_preds.get()
        self.config['verbose'] = self.verbose.get()
        

        # write settings
        logger.debug('writing config...')
        self.gconf['prev_query_path'] = self.dir.get()
        self.gconf['prev_query_mln':self.dir.get()] = self.selected_mln.get()
        self.gconf.dump()
        self.config.dump()
        
        # hide main window
        self.master.withdraw()

        try:
            watch = StopWatch()
            print headline('PRAC QUERY TOOL')
            watch.tag('inference')
            print
            # expand the parameters
            params = dict(self.config.config)
            if 'params' in params:
                params.update(eval("dict(%s)" % params['params']))
                del params['params']
            print tabulate(sorted(list(params.viewitems()), key=lambda (k,v): str(k)), headers=('Parameter:', 'Value:'))
            # create the MLN and evidence database and the parse the queries
            modelstr = mln_content + (emln_content if self.config['use_emln'] not in (None, '') and emln_content != '' else '')
            mln = parse_mln(modelstr, searchPath=self.dir.get(), logic=self.config['logic'], grammar=self.config['grammar'])
            db = parse_db(mln, db_content, ignore_unknown_preds=params.get('ignore_unknown_preds', False))
            if type(db) is list and len(db) > 1:
                raise Exception('Inference can only handle one database at a time')
            else:
                db = db[0]
            # parse non-atomic params
            queries = parse_queries(mln, str(self.config['queries']))
            cw_preds = filter(lambda x: x != "", map(str.strip, str(params["cw_preds"].split(",")))) if 'cw_preds' in params else []
            profile = ifNone(self.config['profile'], False)
            if self.config['cw']:
                cw_preds = [p.name for p in mln.predicates if p.name not in queries]
            
            # extract and remove all non-algorithm
            method = params.get('method', 'MC-SAT')
            for s in GUI_SETTINGS:
                if s in params: del params[s]
            
            if profile:
                prof = Profile()
                print 'starting profiler...'
                prof.enable()
            # set the debug level
            olddebug = praclog.level()
            praclog.level(eval('logging.%s' % params.get('debug', 'WARNING').upper()))
            try:
                mln_ = mln.materialize(db)
                mrf = mln_.ground(db, cwpreds=cw_preds)
                if params.get('verbose', False):
                    print
                    print headline('EVIDENCE VARIABLES')
                    print
                    mrf.print_evidence_vars()
                inference = eval(InferenceMethods.byName(method))(mrf, queries, **params)
                inference.run()
                print 
                print headline('INFERENCE RESULTS')
                print
                inference.write()
                if self.config['save']:
                    with open(os.path.join(self.dir.get(), output), 'w+') as outFile:
                        inference.write(outFile)
            except SystemExit:
                print 'Cancelled...'
            finally:
                if profile:
                    prof.disable()
                    print headline('PROFILER STATISTICS')
                    ps = pstats.Stats(prof, stream=sys.stdout).sort_stats('cumulative')
                    ps.print_stats()
                # reset the debug level
                praclog.level(olddebug)
            print
            watch.finish()
            watch.printSteps()
            
        except:
            traceback.print_exc()
        
        # restore main window
        self.master.deiconify()
        self.set_window_loc()

        sys.stdout.flush()

# -- main app --

if __name__ == '__main__':
    praclog.level(praclog.WARNING)
    
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
