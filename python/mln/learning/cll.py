# COMPOSITE LIKELIHOOD LEARNING
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

from mln.learning.common import AbstractLearner, DiscriminativeLearner
import random
import logging
from mln.learning.bpll import BPLL
from collections import defaultdict
from mln.util import fsum
from numpy.ma.core import log, exp, sqrt
import numpy


class CLL(AbstractLearner):
    '''
    Implementation of composite-log-likelihood learning.
    '''
    
    def __init__(self, mln, mrf=None, **params):
        AbstractLearner.__init__(self, mln, mrf, **params)
        self.partSize = params.get('partSize', 1)
        self.partitions = []
        self.mrf._getPllBlocks()
        self.statistics = {}
        self.partRelevantFormulas = defaultdict(set)
        self.evidenceIndices = {} # maps partition idx to index of value given by evidence
        self.partValueCount = {}
                
                
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
    
    
    def _createVariables(self):
        self.atomicVariables = list(self.mrf.pllBlocks)
        
        
    def _prepareOpt(self):
        log = logging.getLogger(self.__class__.__name__)
        # create random partition of the ground atoms
        self._createVariables()
        variables = self.atomicVariables
        random.shuffle(variables)
        self.partitions = []
        size = self.partSize
        log.debug('variables: %s' % variables)
        while len(variables) > 0:
            vars = variables[:size if len(variables) > size else len(variables)]
            part = map(lambda v: v[0] if v[0] is not None else v[1], vars)
            log.debug('created partition: %s' % str(part))
            self.partitions.append(part)
            variables = variables[len(part):]
        log.debug('composite likelihood learning established %d partitions' % len(self.partitions))
        self._computeStatistics()
        
        
    def _setEvidence(self, evidence, gndAtomIdx, truth=None):
        if gndAtomIdx in self.mrf.gndBlockLookup:
            if truth is not None and truth != 1.:
                raise Exception('Cannot set a mutex variable to truth value %s' % str(truth))
            blockName = self.mrf.gndBlockLookup[gndAtomIdx]
            atomIdxInBlock = self.mrf.gndBlocks[blockName]
            for idx in atomIdxInBlock:
                evidence[idx] = .0 if idx != gndAtomIdx else 1.
        else:
            evidence[gndAtomIdx] = truth
        
        
    def _iterPartitionValues(self, partIdx):
        for value in self._iterPartitionValuesRec(self.partitions[partIdx], self.mrf.evidence):
            yield value
        
    
    def _iterPartitionValuesRec(self, variables, evidence):
        '''
        variables (list):    list of remaining variables
        '''
        evidence = list(evidence)
        if len(variables) == 0:
            yield evidence
            return
        variable = variables[0]
        if type(variable) is list: # this is a block var
            for atom in variable:
                self._setEvidence(evidence, atom)
                for ev in self._iterPartitionValuesRec(variables[1:], evidence):
                    yield ev
        else:
            for truth in (self.mrf.evidence[variable], 1. - self.mrf.evidence[variable]):
                self._setEvidence(evidence, variable, truth)
                for ev in self._iterPartitionValuesRec(variables[1:], evidence):
                    yield ev
            
    def addStatistics(self, fIdx, partIdx, valIdx, size, inc=1.):
        part2values = self.statistics.get(fIdx, None)
        if part2values is None:
            part2values = {}
            self.statistics[fIdx] = part2values
        valuesCounts = part2values.get(partIdx, None)
        if valuesCounts is None:
            valuesCounts = [0] * size
            part2values[partIdx] = valuesCounts
        valuesCounts[valIdx] += inc
        

    def _computeStatistics(self):
        log = logging.getLogger(self.__class__.__name__)
        log.info('Computing statistics...')
        self.statistics = {} # maps formula index to a dict of variables
        # collect for each partition the set of relevant ground formulas
        self.var2GFs = {}
        for i, part in enumerate(self.partitions):
            gfs_ = self.var2GFs.get(i, [])
            for var in part: 
                if type(var) is int:
                    var = [var]
                for gndAtomIdx in var:
                    gfs = self.mrf.gndAtomOccurrencesInGFs[gndAtomIdx]
                    gfs_.extend(filter(lambda x: x not in gfs_, gfs))
                    self.var2GFs[i] = gfs_
        # collect the statistics
        for partIdx, p in enumerate(self.partitions):
            values = list(self._iterPartitionValues(partIdx))
            self.partValueCount[partIdx] = len(values)
            for valIdx, val in enumerate(values):
                if val == self.mrf.evidence:
                    self.evidenceIndices[partIdx] = valIdx
                for gf in self.var2GFs[partIdx]:
                    truth = gf.isTrue(val)
                    self.addStatistics(gf.fIdx, partIdx, valIdx, len(values), truth)
                    self.partRelevantFormulas[partIdx].add(gf.fIdx)


    def _computeProbabilities(self, w):
        probs = {}
        for partIdx in range(len(self.partitions)):
            sums = numpy.zeros(self.partValueCount[partIdx])
            total = 0.
            for f in self.partRelevantFormulas[partIdx]:
                for i, v in enumerate(self.statistics[f][partIdx]):
                    val = v * w[f]
                    sums[i] += val
                    total += val
            if total == 0:
                probs[partIdx] = numpy.array([1. / self.partValueCount[partIdx]] * self.partValueCount[partIdx])
                continue
            sum_min = numpy.min(sums)
            sums -= sum_min
            sum_max = numpy.max(sums)
            sums -= sum_max
            expsums = numpy.sum(numpy.exp(sums))
            s = numpy.log(expsums)
            probs[partIdx] = numpy.exp(sums - s)
#         print probs
        return probs
        

    def _f(self, w):
        probs = self._computeProbabilities(w)
        likelihood = numpy.zeros(len(self.partitions))
        for partIdx in range(len(self.partitions)):
            p = probs[partIdx][self.evidenceIndices[partIdx]]
            if p == 0: p = 1e-10
            likelihood[partIdx] += p
        return fsum(map(log, likelihood))
        
    
    def _grad(self, w):    
        log = logging.getLogger(self.__class__.__name__)
        probs = self._computeProbabilities(w)
        grad = numpy.zeros(len(w), numpy.float64)
        for fIdx, partitions in self.statistics.iteritems():
            for part, values in partitions.iteritems():
                v = values[self.evidenceIndices[part]]
                for i, val in enumerate(values):
                    v -= probs[part][i] * val
                grad[fIdx] += v
#         log.info(grad)
        self.grad_opt_norm = float(sqrt(fsum(map(lambda x: x * x, grad))))
        return numpy.array(grad)
    
    
    def __printPartitions(self):
        log = logging.getLogger(self.__class__.__name__)
        for idx, p in enumerate(self.partitions):
            log.info([self.mrf.gndAtomsByIdx[i] if type(i) is int else map(lambda x: str(self.mrf.gndAtomsByIdx[x]), i) for i in p])
            for evidence in self._iterPartitionValues(idx):
                log.info('VALUE')
                for a in p:
                    if type(a) is list:
                        val = self.mrf.gndAtomsByIdx[a[[v for i, v in enumerate(evidence) if i in a].index(1)]]
                        log.info('  %s = %.1f' % (val, 1.))
                    else:
                        log.info('  %s = %.1f' % (str(self.mrf.gndAtomsByIdx[a]), evidence[a]))
        

class DCLL(CLL, DiscriminativeLearner):
    '''
    Discriminative Composite-Likelihood Learner.
    '''
    
    def __init__(self, mln, mrf=None, **params):
        log = logging.getLogger(self.__class__.__name__)
        CLL.__init__(self, mln, mrf, **params)
        self.queryPreds = self._getQueryPreds(params)
        log.info('query preds: %s' % self.queryPreds)
        
    
    def _createVariables(self):
        self.atomicVariables = filter(lambda block: self._getPredNameForPllBlock(block) in self.queryPreds, self.mrf.pllBlocks)
    
    
    
