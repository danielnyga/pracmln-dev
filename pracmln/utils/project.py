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
from zipfile import ZipFile, ZIP_DEFLATED
import os
import sys
from pracmln.utils.config import PRACMLNConfig
from pracmln.mln.util import out


class MLNProject(object):
    '''
    Represents a .pracmln project archive containing MLNs, DBs and config files.
    '''
    
    def __init__(self, name=None):
        self.name = name
        self._mlns = {}
        self.learnconf = PRACMLNConfig()
        self.queryconf = PRACMLNConfig()
        self._emlns = {}
        self._dbs = {}
        self.dirty = False
        
        
    @property
    def mlns(self):
        return self._mlns
    
    
    @mlns.setter
    def mlns(self, mlns):
        self._mlns = mlns
        self.dirty = True
    
        
    @property
    def dbs(self):
        return self._dbs
    
    
    @dbs.setter
    def dbs(self, dbs):
        self._dbs = dbs
        self.dirty = True
        
        
    @property
    def emlns(self):
        return self._emlns
    
    
    @emlns.setter
    def emlns(self, emlns):
        self._emlns = emlns
        self.dirty = True
        
    
    def add_mln(self, name, content=''):
        self._mlns[name] = content
        self.dirty = True
    
    
    def add_db(self, name, content=''):
        self._dbs[name] = content
        self.dirty = True

    
    def add_emln(self, name, content=''):
        self._emlns[name] = content
        self.dirty = True
        
    
    def rm_mln(self, name):
        del self._mlns[name]
        self.dirty = True
    
    
    def rm_db(self, name):
        del self._dbs[name]
        self.dirty = True
        
    
    def rm_emln(self, name):
        del self._emln[name]
        self.dirty = True
        
    
    def save(self, dirpath='.'):
        filename = '%s.pracmln' % self.name
        with ZipFile(os.path.join(dirpath, filename), 'w', ZIP_DEFLATED) as zf:
            # save the learn.conf
            zf.writestr('learn.conf', self.learnconf.dumps())
            # save the query.conf
            zf.writestr('query.conf', self.queryconf.dumps())
            # save the MLNs
            for name, mln in self.mlns.iteritems():
                zf.writestr(os.path.join('mlns', name), mln)
            # save the model extensions
            for name, emln in self.emlns.iteritems():
                zf.writestr(os.path.join('emlns', name), emln)
            # save the DBs
            for name, db in self.dbs.iteritems():
                zf.writestr(os.path.join('dbs', name), db)
        
    
    @staticmethod
    def open(filepath):
        name = os.path.basename(filepath)
        name = '.'.join(name.split('.')[:-1])
        proj = MLNProject(name)
        with ZipFile(filepath, 'r') as zf:
            for member in zf.namelist():
                if member == 'learn.conf':
                    proj.learnconf = PRACMLNConfig(zf.open(member).read())
                elif member == 'query.conf':
                    proj.queryconf = PRACMLNConfig(zf.open(member).read())
                else:
                    path, f = os.path.split(member)
                    if path == 'mlns':
                        proj._mlns[f] = zf.open(member).read()
                    elif path == 'emlns':
                        proj._emlns[f] = zf.open(member).read()
                    elif path == 'dbs':
                        proj._dbs[f] = zf.open(member).read()
        return proj
        

    def write(self, stream=sys.stdout):
        stream.write('MLN Project: %s\n' % self.name)
        if self.learnconf is not None:
            stream.write('learn.conf\n')
        if self.queryconf is not None:
            stream.write('query.conf\n')
        stream.write('mlns/\n')
        for name in self.mlns:
            stream.write('  ./%s\n' % name)
        stream.write('dbs/\n')
        for name in self.dbs:
            stream.write('  ./%s\n' % name)
        stream.write('emlms/\n')
        for name in self.emlns:
            stream.write('  ./%s\n' % name)
        
        
if __name__ == '__main__':
#     proj = MLNProject('myproject')
#     proj.add_mln('model.mln', '// predicate declarations\nfoo(x)')
#     proj.add_db('data.db', 'foox(X)')
#     proj.save()
    proj = MLNProject.open('myproject.pracmln')
    proj.write()
    
    
    