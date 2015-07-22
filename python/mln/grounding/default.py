# Markov Logic Networks - Default Grounding
#
# (C) 2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
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

from common import AbstractGroundingFactory
import logging
from mln.util import fstr, dict_union, StopWatch, ProgressBar
from logic.common import Logic
import time
from mln.constants import auto, HARD
from mln.errors import SatisfiabilityException


logger = logging.getLogger(__name__)

CACHE_SIZE = 100000

class DefaultGroundingFactory:
    '''
    Implementation of the default grounding algorithm, which
    creates ALL ground atoms and ALL ground formulas.
    '''
    
    def __init__(self, mrf, formulas=None, cache=auto, **params):
        self.mrf = mrf
        self.formulas = self.mrf.formulas if formulas is None else formulas
        self._cachesize = CACHE_SIZE if cache is auto else cache
        self._cache = None
        self.__cacheinit = False
        self._params = params
        self.watch = StopWatch()
        
        
    @property
    def verbose(self):
        return self._params.get('verbose', False)
    
    
    @property
    def multicore(self):
        return self._params.get('multicore', False)
    
    
    @property
    def iscached(self):
        return self._cache is not None and self.__cacheinit

    
    @property
    def usecache(self):
        return self._cachesize is not None and self._cachesize > 0
    
    
    def _cacheinit(self):
        total = 0
        for f in self.formulas:
            total += f.countgroundings(self.mrf)
        if total > self._cachesize:
            logging.getLogger(self.__class__.__name__).warning('Number of formula groundings (%d) exceeds cache size (%d). Caching is disabled.' % (total, self._cachesize))
        else:
            self._cache = []
        self.__cacheinit = True
    
    
    def itergroundings(self, simplify=False, unsatfailure=False):
        '''
        Iterates over all formula groundings.
        
        :param simplify:        if `True`, the formula will be simplified according to the
                                evidence given.
        :param unsatfailure:    raises a :class:`mln.errors.SatisfiabilityException` if a 
                                hard logical constraint is violated by the evidence.
        '''
        if self.iscached:
            for gf in self._cache:
                yield gf
            return
        else:
            if self.usecache and not self.iscached:
                self._cacheinit()
            self.watch.tag('grounding', verbose=self.verbose)
            if self.verbose: 
                bar = ProgressBar(width=100, color='green')
            for i, formula in enumerate(self.formulas):
                if self.verbose: bar.update((i+1) / float(len(self.formulas)))
                for gndformula in formula.itergroundings(self.mrf, simplify=simplify):
                    if self._cache is not None:
                        self._cache.append(gndformula)
                    if unsatfailure and gndformula.weight == HARD and gndformula(self.mrf.evidence) != 1:
                        print
                        gndformula.print_structure(self.mrf.evidence)
                        raise SatisfiabilityException('MLN is unsatisfiable due to hard constraint violation %s (see above)' % self.mrf.formulas[gndformula.idx])
                    yield gndformula
            self.watch.finish('grounding')
        
            
class EqualityConstraintGrounder(object):
    '''
    Grounding factory for equality constraints only.
    '''
    
    def __init__(self, mln, domains, *eq_constraints):
        '''
        Initialize the equality constraint grounder with the given MLN
        and formula. A formula is required that contains all variables
        in the equalities in order to infer the respective domain names.
        '''
        self.constraints = eq_constraints
        self.vardomains = domains
        self.mln = mln
    
    def iter_true_variable_assignments(self):
        '''
        Yields all variable assignments for which all equality constraints
        evaluate to true.
        '''
        for a in self._iter_true_variable_assignments(self.vardomains.keys(), {}, self.constraints):
            yield a
    
    def _iter_true_variable_assignments(self, variables, assignments, eq_groundings):
        if not variables: 
            yield assignments
            return
        variable = variables[0]
        for value in self.mln.domains[self.vardomains[variable]]:
            new_eq_groundings = []
            continue_ = True
            for eq in eq_groundings:
                geq = eq.ground(None, {variable: value}, allowPartialGroundings=True)
                if geq.isTrue(None) == 0:
                    continue_ = False
                    break
                new_eq_groundings.append(geq)
            if not continue_: continue
            for assignment in self._iter_true_variable_assignments(variables[1:], dict_union(assignments, {variable: value}), new_eq_groundings):
                yield assignment
    
    @staticmethod
    def getVarDomainsFromFormula(mln, formula, *varnames):
        if isinstance(formula, basestring):
            formula = mln.logic.parseFormula(formula)
        vardomains = {}
        f_vardomains = formula.getVariables(mln)
        for var in varnames:
            if var not in f_vardomains:
                raise Exception('Variable %s not bound to a domain by formula %s' % (var, fstr(formula)))
            vardomains[var] = f_vardomains[var]
        return vardomains
                
        
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    