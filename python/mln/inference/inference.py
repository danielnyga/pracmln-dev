# Markov Logic Networks -- Inference
#
# (C) 2006-2013 by Daniel Nyga  (nyga@cs.uni-bremen.de)
#                  Dominik Jain (jain@cs.tum.edu)
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

import time

from mln.util import *
from logic.common import Logic
from praclog import logging
import sys
from mln.database import Database
from mln.mrf import temporary_evidence
from mln.constants import ALL
from mln.mrfvars import MutexVariable, SoftMutexVariable


class Inference(object):
    '''
    Represents a super class for all inference methods.
    Also provides some convenience methods for collecting statistics
    about the inference process and nicely outputting results.
    '''
    
    def __init__(self, mrf, queries=ALL, **params):
        self.mrf = mrf
        self.mln = mrf.mln 
        self._params = params
        if queries == ALL:
            self.queries = [self.mln.logic.gnd_lit(ga, negated=False, mln=self.mln) for ga in self.mrf.gndatoms if self.mrf.evidence[ga.idx] is None]
        else:
            # check for single/multiple query and expand
            if type(queries) is not list:
                queries = [queries]
            self.queries = self._expand_queries(queries)
        self._watch = StopWatch()
    
    
    @property
    def verbose(self):
        return self._params.get('verbose', False)
    
    @property
    def results(self):
        if self._results is None:
            raise Exception('No results available. Run the inference first.')
        else:
            return self._results
        
    @property
    def elapsedtime(self):
        return self._watch['inference'].elapsedtime
        
        
    @property
    def multicore(self):
        return self._params.get('multicore')
    
    
    @property
    def resultdb(self):
        db = Database(self.mrf.mln)
        for atom in sorted(self.results, key=str):
            db[str(atom)] = self.results[atom]
        return db
    

#     @property
#     def closedworld(self):
#         self._params.get('closedworld', None)
        

    def _expand_queries(self, queries):
        ''' 
        Expands the list of queries where necessary, e.g. queries that are 
        just predicate names are expanded to the corresponding list of atoms.
        '''
        equeries = []
        logger = logging.getLogger(self.__class__.__name__)
        for query in queries:
            if type(query) == str:
                prevLen = len(equeries)
                if '(' in query: # a fully or partially grounded formula
                    f = self.mln.logic.parse_formula(query)
                    for gf in f.itergroundings(self.mrf):
                        equeries.append(gf)
                else: # just a predicate name
                    if query not in self.mln.prednames:
                        logger.warning('Unsupported query: %s is not among the admissible predicates.' % (query))
                        continue
                    for gndatom in self.mln.predicate(query).groundatoms(self.mln, self.mrf.domains):
                        equeries.append(self.mln.logic.gnd_lit(self.mrf.gndatom(gndatom), negated=False, mln=self.mln))
                if len(equeries) - prevLen == 0:
                    raise Exception("String query '%s' could not be expanded." % query)
            elif isinstance(query, Logic.Formula):
                equeries.append(query)
            else:
                raise Exception("Received query of unsupported type '%s'" % str(type(query)))
        return equeries
    
    
    def _run(self, verbose=False, **args):
        raise Exception('%s does not implement _infer()' % self.__class__.__name__)


    def run(self):
        '''
        Starts the inference process.
        '''
        
        # perform actual inference (polymorphic)
        if self.verbose: print 'Inference engine: %s' % self.__class__.__name__
        self._watch.tag('inference', verbose=self.verbose)
#         if self.closedworld is not None:
#             with temporary_evidence(self.mrf):
#                 self.mrf.apply_cw(None if self.closedworld is ALL else self.closedworld)
        self._results = self._run()
        self._watch.finish('inference')
        return self
    
    
    def write(self, stream=sys.stdout, color=None, sort='prob', group=True, reverse=True):
        barwidth = 30
        if stream is sys.stdout and color is None:
            color = 'yellow'
        if sort not in ('alpha', 'prob'):
            raise Exception('Unknown sorting: %s' % sort)
        results = dict(self.results)
        if group:
            for var in sorted(self.mrf.variables, key=str):
                res = dict([(atom, prob) for atom, prob in results.iteritems() if atom in map(str, var.gndatoms)])
                if not res: continue
                if isinstance(var, MutexVariable) or isinstance(var, SoftMutexVariable):
                    stream.write('%s:\n' % var)
                if sort == 'prob':
                    res = sorted(res, key=self.results.__getitem__, reverse=reverse)
                elif sort == 'alpha':
                    res = sorted(res, key=str)
                for atom in res:
                    stream.write('%s %s\n' % (barstr(barwidth, self.results[atom], color=color), atom))
            return
        # first sort wrt to probability
        results = sorted(results, key=self.results.__getitem__, reverse=reverse)
        # then wrt gnd atoms
        results = sorted(results, key=str)
        for q in results:
            stream.write('%s %s\n' % (barstr(barwidth, self.results[q], color=color), q))
    
    
    def write_elapsed_time(self, stream=sys.stdout, color=None):
        if stream is sys.stdout and color is None:
            color = True
        elif color is None:
            color = False
        if color: col = 'blue'
        else: col = None
        total = float(self._watch['inference'].elapsedtime)
        stream.write(colorize('INFERENCE RUNTIME STATISTICS\n============================\n', format=(None, None, True), color=color))
        for t in sorted(self._watch.tags.values(), key=lambda t: t.elapsedtime, reverse=True):
            stream.write('%s %s %s\n' % (barstr(width=30, percent=t.elapsedtime / total, color=col), elapsed_time_str(t.elapsedtime), t.label))
    
    


