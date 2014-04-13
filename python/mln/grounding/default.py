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
from mln.util import strFormula
from logic.common import Logic
import time

class DefaultGroundingFactory(AbstractGroundingFactory):
    '''
    Implementation of the default grounding algorithm, which
    creates ALL ground atoms and ALL ground formulas.
    '''
    
    def __init__(self, mrf, db, **params):
        AbstractGroundingFactory.__init__(self, mrf, db, **params)
        self.formula2GndFormulas = {}
        
    
    def _createGroundAtoms(self):
        # create ground atoms
        for predName, domNames in self.mln.predicates.iteritems():
            self._groundAtoms([], predName, domNames)


    def _groundAtoms(self, cur, predName, domNames):
        # if there are no more parameters to ground, we're done
        # and we cann add the ground atom to the MRF
        mrf = self.mrf
        assert len(mrf.gndFormulas) == 0
        if domNames == []:
            atom = mrf.mln.logic.gnd_atom(predName, cur)
            mrf.addGroundAtom(atom)
            return True
        log = logging.getLogger(self.__class__.__name__)
        # create ground atoms for each way of grounding the first of the 
        # remaining variables whose domains are given in domNames
        dom = mrf.domains.get(domNames[0])
        if dom is None or len(dom) == 0:
            log.info("Ground Atoms for predicate %s could not be generated, since the domain '%s' is empty" % (predName, domNames[0]))
            return False
        for value in dom:
            if not self._groundAtoms(cur + [value], predName, domNames[1:]): return False
        return True

        
    def _createGroundFormulas(self):
        mrf = self.mrf
        assert len(mrf.gndAtoms) > 0
        log = logging.getLogger(self.__class__.__name__)
        # generate all groundings
        log.info('Grounding formulas...')
        log.debug('Ground formulas (all should have a truth value):')
        self.gndTime = time.time()
        for idxFormula, formula in enumerate(mrf.formulas):
            for gndFormula, _ in formula.iterGroundings(mrf, mrf.simplify):
                gndFormula.isHard = formula.isHard
                gndFormula.weight = formula.weight
                gndFormula.fIdx = idxFormula
                mrf._addGroundFormula(gndFormula, idxFormula, None)
        self.gndTime = time.time() - self.gndTime
