# MARKOV LOGIC NETWORKS -- VOTED PERCEPTORN LEARNING
#
# (C) 2011-2014 by Daniel Nyga (nyga@cs.uni-bremen.de)
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

from mln.learning.common import AbstractLearner
from mln.database import Database
from wcsp.converter import WCSPConverter
from praclog import logging
import numpy
import random

class VP(AbstractLearner):
    '''
    Log-likelihood learning with Voted Perceptron approximation.
    In this approach, the intractable expectation of true groundings
    in the weight gradient is approximated by the MPE state.
    '''
    
    def __init__(self, mln, mrf, **params):
        AbstractLearner.__init__(self, mln, mrf)
        # initialize the weights randomly
        self.initialWts = True
        for f in mln.formulas:
            f.weight = (random.random() - .5) * 0.01 
        

    def _prepareOpt(self):
        log = logging.getLogger(self.__class__.__name__)
        self.trueGroundings = [0] * len(self.mln.formulas)
        for gndFormula in self.mrf.gndFormulas:
            self.trueGroundings[gndFormula.idxFormula] += gndFormula.isTrue(self.mrf.evidence)
        # the dummy database holds only the evidence atoms
        # and the domains must be transferred.
        self.dummyDB = Database(self.mln)
        self.dummyDB.domains = dict(self.mrf.domains)
        log.info(self.params)
        for pred in [p for p in self.mln.predicates if not p in self.params['queryPreds']]:
            for atom in self.mrf._getPredGroundings(pred):
                self.dummyDB.addGroundAtom(atom, self.mrf.evidence[self.mrf.gndAtoms[atom].idx])
#         log.debug(self.trueGroundings)
        self.wt_hist = []
        
    def _postProcess(self):
        self.wt = numpy.array([0.] * len(self.wt))
        for w in self.wt_hist:
            self.wt += w
        self.wt /= float(len(self.wt_hist))

    def _grad(self, wt):
        log = logging.getLogger(self.__class__.__name__)
        mln = self.mln.duplicate()
        mln.setWeights(wt)
        self.wt_hist.append(numpy.array(wt))
        log.debug('wt=%s' % str(wt))
        log.debug(mln.formulas)
        mrf = mln.groundMRF(self.dummyDB)
#         for gf in mrf.gndFormulas:
#             log.info(gf)
        conv = WCSPConverter(mrf)
        resultDB = conv.getMostProbableWorldDB()
#         for e in mrf.gndAtoms:
#             log.info('%s\t\t%s <-> %s' % (e, str(resultDB.evidence.get(e, 0)), str(self.mrf.evidence[self.mrf.gndAtoms[e].idx])))
        trueGroundings = [0] * len(mln.formulas)
#         mrf.printEvidence()    
        mrf.setEvidence(resultDB.evidence, cwAssumption=True)
        for gndFormula in self.mrf.gndFormulas:
            trueGroundings[gndFormula.idxFormula] += gndFormula.isTrue(mrf.evidence)
        return numpy.array([t - n for t, n in zip(self.trueGroundings, trueGroundings)])
    
        
    def useF(self):
        return False
    