# MARKOV LOGIC NETWORKS
#
# (C) 2011-2014 by Daniel Nyga (nyga@cs.tum.edu)
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

from pracmln.mln.grounding.default import DefaultGroundingFactory
import logging
from pracmln.logic.common import Logic
import types
from multiprocessing.pool import Pool
from pracmln.utils.multicore import with_tracing
from itertools import imap
import itertools
from pracmln.mln.mlnpreds import FunctionalPredicate, SoftFunctionalPredicate
from pracmln.mln.util import fstr, dict_union, stop, out
from pracmln.mln.errors import SatisfiabilityException
from pracmln.mln.constants import HARD, auto
from collections import defaultdict

logger = logging.getLogger(__name__)
    
# this readonly global is for multiprocessing to exploit copy-on-write
# on linux systems
global_fastConjGrounding = None

# multiprocessing function
def create_formula_groundings(formula):
    gfs = []
    if global_fastConjGrounding.mrf.mln.logic.islitconj(formula) or global_fastConjGrounding.mrf.mln.logic.isclause(formula):
        for gf in global_fastConjGrounding.itergroundings_fast(formula):
            gfs.append(gf)
    else:
        for gf in formula.itergroundings(global_fastConjGrounding.mrf, simplify=True):
            gfs.append(gf)
    return gfs
    
def pivot(t):
    if t == 'conj':
        return min
    elif t == 'disj':
        return max

class FastConjunctionGrounding(DefaultGroundingFactory):
    '''
    Fairly fast grounding of conjunctions pruning the grounding tree if a formula
    is rendered false by the evidence. Performs some heuristic sorting such that
    equality constraints are evaluated first.
    '''
    
    def __init__(self, mrf, simplify=False, unsatfailure=False, formulas=None, cache=auto, **params):
        DefaultGroundingFactory.__init__(self, mrf, simplify=simplify, unsatfailure=unsatfailure, formulas=formulas, cache=cache, **params)
            
    
    def _conjsort(self, e):
        if isinstance(e, Logic.Equality):
            return 2.5
        elif isinstance(e, Logic.TrueFalse):
            return 1
        elif isinstance(e, Logic.GroundLit):
            if self.mrf.evidence[e.gndatom.idx] is not None:
                return 2
            elif type(self.mrf.mln.predicate(e.gndatom.predname)) in (FunctionalPredicate, SoftFunctionalPredicate):
                return 3
            else:
                return 4
        elif isinstance(e, Logic.Lit) and type(self.mrf.mln.predicate(e.predname)) in (FunctionalPredicate, SoftFunctionalPredicate):
            return 5
        elif isinstance(e, Logic.Lit):
            return 6
        else:
            return 7
        
    
    def itergroundings_fast(self, formula):
        '''
        Recursively generate the groundings of a conjunction that do _not_
        have a definite truth value yet given the evidence.
        '''
        # make a copy of the formula to avoid side effects
        formula = formula.ground(self.mrf, {}, partial=True)
        if self.mrf.mln.logic.isclause(formula):
            t = 'disj'
        elif self.mrf.mln.logic.islitconj(formula):
            t = 'conj'
        else:
            raise Exception('Unexpected formula: %s' % fstr(formula))
        children = [formula] if  not hasattr(formula, 'children') else formula.children
        # make equality constraints access their variable domains
        # this is a _really_ dirty hack but it does the job ;-)
        variables = formula.vardoms()
        def eqvardoms(self, v=None, c=None):
            if v is None:
                v = defaultdict(set)
            for a in self.args:
                if self.mln.logic.isvar(a):
                    v[a] = variables[a]
            return v 
        for child in children:
            if isinstance(child, Logic.Equality):
                # replace the vardoms method in this equality instance
                # by our customized one
                setattr(child, 'vardoms', types.MethodType(eqvardoms, child))
        lits = sorted(children, key=self._conjsort)
        for gf in self._itergroundings_fast(t, formula, variables, lits, gndlits=[], truthpivot=1 if t == 'conj' else 0, assignment={}):
            yield gf
            
            
    def _itergroundings_fast(self, typ, formula, domains, lits, gndlits, assignment, truthpivot, level=0):
        if truthpivot == 0 and typ == 'conj':
            if formula.weight == HARD:
                raise SatisfiabilityException('MLN is unsatisfiable given evidence due to hard constraint violation: %s' % fstr(formula))
            return
        if truthpivot == 1 and typ == 'disj':
            return
        if not lits:
            if len(gndlits) == 1:
                gf = gndlits[0].simplify(self.mrf.evidence)
            elif typ == 'conj':
                gf = self.mrf.mln.logic.conjunction(gndlits, mln=self.mrf.mln, idx=formula.idx).simplify(self.mrf.evidence)
            elif typ == 'disj':
                gf = self.mrf.mln.logic.disjunction(gndlits, mln=self.mrf.mln, idx=formula.idx).simplify(self.mrf.evidence)
            if isinstance(gf, Logic.TrueFalse): 
                if gf.weight == HARD and gf.value < 1:
                    raise SatisfiabilityException('MLN is unsatisfiable given evidence due to hard constraint violation: %s' % fstr(formula))
            else: 
                yield gf
            return
        lit = lits[0]
        lit = lit.ground(self.mrf, assignment, partial=True)
        if isinstance(lit, Logic.Equality):
            def eqvardoms(self, v=None, c=None):
                if v is None:
                    v = defaultdict(set)
                for a in self.args:
                    if self.mln.logic.isvar(a):
                        v[a] = domains[a]
                return v 
            setattr(lit, 'vardoms', types.MethodType(eqvardoms, lit))

        for varass in lit.itervargroundings(self.mrf):
            ga = lit.ground(self.mrf, varass)
            for gf in self._itergroundings_fast(typ, formula, domains, lits[1:], gndlits + [ga], dict_union(assignment, varass), pivot(typ)(truthpivot, ga.truth(self.mrf.evidence)), level+1):
                yield gf
            
        
    def _itergroundings(self, simplify=True, unsatfailure=True):
        # generate all groundings
        global global_fastConjGrounding
        global_fastConjGrounding = self
        if self.multicore:
            pool = Pool()
            for gfs in pool.imap(with_tracing(create_formula_groundings), self.formulas):
                for gf in gfs: yield gf
            pool.terminate()
            pool.join()
        else:
            for gfs in imap(create_formula_groundings, self.formulas):
                for gf in gfs: yield gf

            