# 
#
# (C) 2011-2015 by Daniel Nyga (nyga@cs.uni-bremen.de)
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
import json
import os
from pracmln import praclog
import traceback
from pracmln.mln.util import out


logger = praclog.logger(__name__)


fixed_width_font = ("Monospace", -12)
learn_config_pattern = '%s.learn.conf'
query_config_pattern = '%s.query.conf'
global_config_filename = '.pracmln.conf'


# --- settings for the parameter learning tool ---

learnwts_mln_filemask = "*.mln"
learnwts_db_filemask = "*.db"
def learnwts_output_filename(infile, engine, method, dbfile): # formats the output filename
    if infile[:3] == "in.": infile = infile[3:]
    elif infile[:4] == "wts.": infile = infile[4:]
    if infile[-4:] == ".mln": infile = infile[:-4]
    if dbfile[-3:] == ".db": dbfile = dbfile[:-3]
    return "wts.%s%s.%s-%s.mln" % (engine, method, dbfile, infile)
learnwts_full_report = True # if True, add all the printed output to the Alchemy output file, otherwise (False) use a short report
learnwts_report_bottom = True # if True, the comment with the report is appended to the end of the file, otherwise it is inserted at the beginning
learnwts_edit_outfile_when_done = False # if True, open the learnt output file that is generated in the editor defined in configGUI

#  --- settings for the query tool ---

query_mln_filemask = "*.mln"
query_db_filemask = ["*.db", "*.blogdb"]
def query_output_filename(mlnfile, dbfile):
    if mlnfile[:4] == "wts.": mlnfile = mlnfile[4:]
    if mlnfile[-4:] == ".mln": mlnfile = mlnfile[:-4]
    if dbfile[-3:] == ".db": dbfile = dbfile[:-3]
    return "%s-%s.results" % (dbfile, mlnfile)
query_edit_outfile_when_done = False # if True, open the output file that is generated by the Alchemy system in the editor defined above


class PRACMLNConfig(object):
    
    def __init__(self, filepath=None):
        if filepath is None: # load the global config file
            self.config_file = os.path.join(os.getenv("PRACMLN_HOME", os.getcwd()), global_config_filename)
        else:
            self.config_file = filepath
        self.config = {}
        if not os.path.exists(self.config_file):
            self.config = {}
        else:
            with open(self.config_file, 'r') as cf:
                self.config = json.load(cf)
                logger.debug('loaded %s config' % self.config_file)
            
    
    def __getitem__(self, s):
        if type(s) is slice:
            prim = s.start
            sec = s.stop
            if self.config.get(prim) is not None:
                return self.config.get(prim).get(sec)
            else:
                return None
        else:
            return self.config.get(s)
        

    def __setitem__(self, s, v):
        if type(s) is slice:
            prim = s.start
            sec = s.stop
            p = self.config.get(prim)
            if p is None:
                p = {}
                self.config[prim] = p
            p[sec] = v
        else:
            self.config[s] = v
            
    
    def dump(self):
        with open(self.config_file, 'w+') as cf:
            json.dump(self.config, cf)

        
        
        