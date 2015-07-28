# -*- coding: utf-8 -*-
#
# Markov Logic Networks
#
# (C) 2006-2012 by Dominik Jain (jain@cs.tum.edu)
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

from common import AbstractLearner
from collections import defaultdict
import numpy
import logging
import time
from pracmln.mln.util import barstr, fsum
from numpy.ma.core import sqrt, log
from pracmln.mln.grounding.default import DefaultGroundingFactory
from pracmln.mln.mrfvars import SoftMutexVariable
from pracmln.mln.learning.common import DiscriminativeLearner


logger = logging.getLogger(__name__)


class BPLL(AbstractLearner):
    '''
    Pseudo-log-likelihood learning with blocking, i.e. a generalization
    of PLL which takes into consideration the fact that the truth value of a
    blocked atom cannot be inverted without changing a further atom's truth
    value from the same block.
    This learner is fairly efficient, as it computes f and grad based only
    on a sufficient statistic.
    '''    
    
    def __init__(self, mrf, **params):
        AbstractLearner.__init__(self, mrf, **params)
        self._pls = None
        self._stat = None
        self._varidx2fidx = None
        self._w = None
        self._lastw = None
        
        
    def _prepare(self):
        logger.debug("computing statistics...") 
        self._compute_statistics()
    
    
    def _pl(self, varidx, w):
        '''
        Computes the pseudo-likelihoods for the given variable under weights w. 
        '''        
        var = self.mrf.variable(varidx)
        values = var.valuecount()
        gfs = self._varidx2fidx.get(varidx)
        if gfs is None: # no list was saved, so the truth of all formulas is unaffected by the variable's value
            # uniform distribution applies
            p = 1.0 / values
            return [p] * values
        sums = numpy.zeros(values)
        for fidx in gfs:
            for validx, n in enumerate(self._stat[fidx][varidx]):
                sums[validx] += n * w[fidx]
        expsums = numpy.exp(sums)
        z = sum(expsums)
        return map(lambda w_: w_ / z, expsums)
#         sum_min = numpy.min(sums)
#         sums -= sum_min
#         sum_max = numpy.max(sums)
#         sums -= sum_max
#         expsums = numpy.sum(numpy.exp(sums))
#         s = numpy.log(expsums)    
#         return numpy.exp(sums - s)
    
    
    def write_pls(self):
        for var in self.mrf.variables:
            print var
            for i, value in var.itervalues():
                print '    ', barstr(width=50, color='magenta', percent=self._pls[var.idx][i]), i, value
    
    
    def _compute_pls(self, w):
        if self._pls is None or self._lastw is None or self._lastw != list(w):
            self._pls = [self._pl(var.idx, w) for var in self.mrf.variables]
#             self.write_pls()
            self._lastw = list(w)
    
    
    def _f(self, w):
        self._compute_pls(w)
        probs = []
        for var in self.mrf.variables:
            p = self._pls[var.idx][var.evidence_value_index()]
            if p == 0: p = 1e-10 # prevent 0 probabilities
            probs.append(p)
        return fsum(map(log, probs))

   
    def _grad(self, w):
        self._compute_pls(w)
        grad = numpy.zeros(len(self.mrf.formulas), numpy.float64)        
        for fidx, varval in self._stat.iteritems():
            for varidx, counts in varval.iteritems():
                evidx = self.mrf.variable(varidx).evidence_value_index()
                g = counts[evidx]
                for i, val in enumerate(counts):
                    g -= val * self._pls[varidx][i]
                grad[fidx] += g
        self.grad_opt_norm = float(sqrt(fsum(map(lambda x: x * x, grad))))
        return numpy.array(grad)

    
    def _addstat(self, fidx, varidx, validx, inc=1):
        if fidx not in self._stat:
            self._stat[fidx] = {}
        d = self._stat[fidx]
        if varidx not in d:
            d[varidx] = [0] * self.mrf.variable(varidx).valuecount()
        d[varidx][validx] += inc
        
    
    def _compute_statistics(self):
        '''
        computes the statistics upon which the optimization is based
        '''
        self._stat = {}
        self._varidx2fidx = defaultdict(set)
        grounder = DefaultGroundingFactory(self.mrf, verbose=False, cache=1000)
        for f in grounder.itergroundings(simplify=False, unsatfailure=True):
            for gndatom in f.gndatoms():
                var = self.mrf.variable(gndatom)
                for validx, value in var.itervalues():
                    truth = f(var.setval(value, self.mrf.evidence)) 
                    if truth != 0:
                        self._varidx2fidx[var.idx].add(f.idx)
                        self._addstat(f.idx, var.idx, validx, truth)
                
        
class BPLL_CG(BPLL):
    '''
        BPLL learner variant that uses a custom grounding procedure to increase
        efficiency.
    '''
    
    groundingMethod = 'BPLLGroundingFactory'
    
    def __init__(self, mln, mrf, **params):
        BPLL.__init__(self, mln, mrf, **params)
    
    def _prepareOpt(self):
        if len(filter(lambda b: isinstance(b, SoftMutexVariable), self.mrf.variables)) > 0:
            raise Exception('%s cannot handle soft-functional constraints' % self.__class__.__name__)
        log = logging.getLogger(self.__class__.__name__)
        log.info("constructing blocks...")
        self.mrf._getPllBlocks()
        self.mrf._getAtom2BlockIdx()
        start = time.time()
        self.mrf.groundingMethod._computeStatistics()
        log.info('Total time: %.2f' % (time.time() - start))
        self.fcounts = self.mrf.groundingMethod.fcounts
        self.blockRelevantFormulas = self.mrf.groundingMethod.blockRelevantFormulas
        self.evidenceIndices = self.mrf.groundingMethod.evidenceIndices
            
            
            
class BPLL_SF(BPLL):
    '''
    BPLL learner variant that uses the new representation of 
    ground atoms and block variables supporting soft functional constraints.
    '''
    
    groundingMethod = 'DefaultGroundingFactory'
    
    def __init__(self, mln, mrf, **params):
        BPLL.__init__(self, mln, mrf, **params)
    
    def _prepareOpt(self):
        log = logging.getLogger(self.__class__.__name__)
        log.info("constructing blocks...") 
        self._computeStatistics()
        # remove data that is now obsolete
        self.mrf.removeGroundFormulaData()
        log.info('Total time: %.2f' % (self.mrf.groundingMethod.gndTime + self.statTime))
    
    
    def _f(self, wt):
        self._calculateBlockProbsMB(wt)
        probs = []
        for idxVar in xrange(len(self.mrf.variables)):
            p = self.blockProbsMB[idxVar][self.evidenceIndices[idxVar]]
            if p == 0: p = 1e-10 # prevent 0 probabilities
            probs.append(p)
        return fsum(map(log, probs))
        
    
    def _calculateBlockProbsMB(self, wt):
        if ('wtsLastBlockProbMBComputation' not in dir(self)) or self.wtsLastBlockProbMBComputation != list(wt):
            #print "recomputing block probabilities...",
            self.blockProbsMB = [self._getBlockProbMB(i, wt) for i in xrange(len(self.mrf.variables))]
#             print self.blockProbsMB
            self.wtsLastBlockProbMBComputation = list(wt)    
    
        
    def _getBlockProbMB(self, blockidx, wt):        
        atomicBlock = self.mrf.variable_by_idx[blockidx]
        numValues = atomicBlock.getNumberOfValues()
        
        relevantFormulas = self.blockRelevantFormulas.get(blockidx, None)
        if relevantFormulas is None: # no list was saved, so the truth of all formulas is unaffected by the variable's value
            # uniform distribution applies
            p = 1.0 / numValues
            return [p] * numValues
        
        sums = numpy.zeros(numValues)
        for idxFormula in relevantFormulas:
            for idxValue, n in enumerate(self.fcounts[idxFormula][blockidx]):
                sums[idxValue] += n * wt[idxFormula]
        sum_min = numpy.min(sums)
        sums -= sum_min
        sum_max = numpy.max(sums)
        sums -= sum_max
        expsums = numpy.sum(numpy.exp(sums))
        s = numpy.log(expsums)
        return numpy.exp(sums - s)
    
        
    def _computeStatistics(self):
        '''
        computes the statistics upon which the optimization is based
        '''
        debug = False
        log = logging.getLogger(self.__class__.__name__)
        log.info("computing statistics...")
        self.statTime = time.time()
        # get evidence indices
        self.evidenceIndices = [None] * len(self.mrf.variables)
        for atomicBlock in self.mrf.variables.values():
            self.evidenceIndices[atomicBlock.blockidx] = atomicBlock.getEvidenceIndex(self.mrf.evidence)
        
        # compute actual statistics
        self.fcounts = {}
        self.blockRelevantFormulas = defaultdict(set) # maps from variable/pllBlock index to a list of relevant formula indices
        for gndFormula in self.mrf.gndFormulas:
            # get the set of block indices that the variables appearing in the formula correspond to
            atomicBlocks = set()
            for idxGA in gndFormula.idxGroundAtoms():
                atomicBlocks.add(self.mrf.gndatom2variable[idxGA])
            
            for atomicBlock in atomicBlocks:
                blocksize = atomicBlock.getNumberOfValues()
                for valueIdx, value in enumerate(atomicBlock.generateValueTuples()):
                    self.mrf.setTemporaryEvidence(atomicBlock.valueTuple2EvidenceDict(value))
                    truth = self.mrf._isTrueGndFormulaGivenEvidence(gndFormula)
                    self._addMBCount(atomicBlock.idx, blocksize, valueIdx, gndFormula.idxFormula, truth)
                    self.mrf._removeTemporaryEvidence()
                    
        self.statTime = time.time() - self.statTime


class DBPLL_CG(BPLL_CG, DiscriminativeLearner):
    '''
    Discriminative Pseudo-likelihood with custom grounding.
    '''
    
    def __init__(self, mln, mrf, **params):
        BPLL_CG.__init__(self, mln, mrf, **params)
        self.queryPreds = self._getQueryPreds(params)
        

    def _f(self, wt):
        self._calculateBlockProbsMB(wt)
        probs = []
        for idxVar, block in enumerate(self.mrf.pllBlocks):
            predName = self._getPredNameForPllBlock(block)
            if not self._isQueryPredicate(predName):
                continue
            p = self.blockProbsMB[idxVar][self.evidenceIndices[idxVar]]
            if p == 0: p = 1e-10 # prevent 0 probabilities
            probs.append(p)
        return fsum(map(log, probs))
   
    def _grad(self, wt):
        self._calculateBlockProbsMB(wt)
        grad = numpy.zeros(len(self.mrf.formulas), numpy.float64)        
        #print "gradient calculation"
        for idxFormula, d in self.fcounts.iteritems():
            for idxVar, counts in d.iteritems():
                block = self.mrf.pllBlocks[idxVar]
                predName = self._getPredNameForPllBlock(block)
                if not self._isQueryPredicate(predName):
                    continue
                val = self.evidenceIndices[idxVar]
                v = counts[val]
                for i in xrange(len(counts)):
                    v -= counts[i] * self.blockProbsMB[idxVar][i]
                grad[idxFormula] += v
        #print "wts =", wt
        #print "grad =", grad
        self.grad_opt_norm = float(sqrt(fsum(map(lambda x: x * x, grad))))
        return numpy.array(grad)
    
    
    
    def _getPredNameForPllBlock(self, block):
        '''
        block being a (gaIdx, [gaIdx, ...]) tuple. 
        '''
        (idxGA, block) = block
        if idxGA is None:
            if len(block) == 0:
                raise Exception('Encountered empty block.')
            else:
                return self.mrf.gndAtomsByIdx[block[0]].predName
        else:
            return self.mrf.gndAtomsByIdx[idxGA].predName
