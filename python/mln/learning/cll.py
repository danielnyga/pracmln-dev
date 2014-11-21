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
from collections import defaultdict
from mln.util import fsum
from numpy.ma.core import log, sqrt
import numpy
from logic.common import Logic
import sys
from utils import dict_union, StopWatch
import types

class CLL(AbstractLearner):
    '''
    Implementation of composite-log-likelihood learning.
    '''
    
    groundingMethod = 'NoGroundingFactory'
    
    def __init__(self, mln, mrf=None, **params):
        AbstractLearner.__init__(self, mln, mrf, **params)
        self.partSize = params.get('partSize', 1)
        self.partitions = []
        self.statistics = {}
        self.partRelevantFormulas = defaultdict(set)
        self.evidenceIndices = {} # maps partition idx to index of value given by evidence
        self.partValueCount = {}
        self.atomIdx2partition = {} # maps a gnd atom index to its comprising partition
        self.maxiter = params.get('maxiter', None)
        self.maxrepart = params.get('maxrepart', 0)
        self.repart = 0
                
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
        '''
        In the this (generative) variant of the learner, atomic variables
        are given by the PLL blocks.
        A discriminative variant can be obtained by filtering out those
        atomic vars that correspond to evidence predicates.
        '''
        self.atomicVariables = list(self.mrf.gndAtomicBlocks.values())
        
        
    def _prepareOpt(self):
        log = logging.getLogger(self.__class__.__name__)
        # create random partition of the ground atoms
        self._createVariables()
        variables = self.atomicVariables
        log.info('repartitioning %d' % self.repart)
        random.shuffle(variables)
        self.partitions = []
        self.atomIdx2partition = {}
        self.evidenceIndices = {}
        self.partValueCount = {}
        self.current_wts = None
        self.iter = 0
        self.probs = None
        size = self.partSize
        while len(variables) > 0:
            vars = variables[:size if len(variables) > size else len(variables)]
#             partVariables = map(lambda v: v[0] if v[0] is not None else v[1], vars)
            partidx = len(self.partitions)
            partition = CLL.GndAtomPartition(self.mrf, vars, partidx)
            # create the mapping from atoms to their partitions
            for atom in partition.getGndAtomsPlain():
                self.atomIdx2partition[atom.idx] = partition
            log.debug('created partition: %s' % str(partition))
            self.partValueCount[partidx] = partition.getNumberOfPossibleWorlds()
            self.partitions.append(partition)
            self.evidenceIndices[partidx] = partition.getEvidenceIndex()
            variables = variables[len(partition.variables):]
        log.debug('CLL created %d partitions' % len(self.partitions))
        self._computeStatistics()
        
        
#     def run(self, **params):
#         '''
#         This is a modification of the run method of the AbstractLearner, which
#         runs the optimization only for a specified number of iterations and
#         then reconfigures the CLL partitions.
#         initialWts: whether to use the MLN's current weights as the starting point for the optimization
#         '''
#          
#         log = logging.getLogger(self.__class__.__name__)
#         if not 'scipy' in sys.modules:
#             raise Exception("Scipy was not imported! Install numpy and scipy if you want to use weight learning.")
#         # initial parameter vector: all zeros or weights from formulas
#         wt = numpy.zeros(len(self.mln.formulas), numpy.float64)
#         if self.initialWts:
#             for i in range(len(self.mln.formulas)):
#                 wt[i] = self.mln.formulas[i].weight
#             log.debug('Using initial weight vector: %s' % str(wt))
#                  
#         # precompute fixed formula weights
#         self._fixFormulaWeights()
#         self.wt = self._projectVectorToNonFixedWeightIndices(wt)
#          
#         self.params.update(params)
#         repart = self.params.get('maxrepart', 5)
#         for i in range(repart):
#             self._prepareOpt()
#             self._optimize(**params)
#             self._postProcess()
#         return self.wt
    
    
    def printStatistics(self):
        for f, parts in self.statistics.iteritems():
#             for val, counts in parts.iteritems():
            print f, parts
    
            
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
        watch = StopWatch()
        watch.tag('grounding')
        self.statistics = {}
        self.partRelevantFormulas = defaultdict(set)
        log = logging.getLogger(self.__class__.__name__)
        for formula in self.mrf.formulas:
            literals = []
            for literal in formula.iterLiterals():
                literals.append(literal)
            # in case of a conjunction, rearrange the literals such that 
            # equality constraints are evaluated first
            isconj = self.mrf.mln.logic.isConjunctionOfLiterals(formula)
            if isconj:
                literals = sorted(literals, key=lambda l: -1 if isinstance(l, Logic.Equality) else 1)
            self._computeStatisticsRecursive(literals, [], {}, formula, isconj=isconj)
        watch.finish()
        watch.printSteps()
    
    
    def _computeStatisticsRecursive(self, literals, gndliterals, var_assign, formula, f_gndlit_parts=None, processed=None, isconj=False):
        '''
        TODO: make sure that there are no equality constraints in the conjunction!
        '''
        log = logging.getLogger(self.__class__.__name__)
        if len(literals) == 0:
            # at this point, we have a fully grounded conjunction in gndliterals
            # create a mapping from a partition to the ground literals in this formula
            # (criterion no. 1, applies to all kinds of formulas)
            part2gndlits = defaultdict(list)
            part_with_f_lit = None
            for gndlit in gndliterals:
                if isinstance(gndlit, Logic.Equality) or hasattr(self, 'queryPreds') and gndlit.gndAtom.predName not in self.queryPreds: continue
                part = self.atomIdx2partition[gndlit.gndAtom.idx]
                part2gndlits[part].append(gndlit)
                if gndlit.isTrue(self.mrf.evidence) == 0:
                    part_with_f_lit = part  
            # if there is a false ground literal we only need to take into account
            # the partition comprising this literal (criterion no. 2)
            # there is maximally one such partition with false literals in the conjunction
            # because of criterion no. 5
            if isconj and part_with_f_lit is not None:
                gndlits = part2gndlits[part_with_f_lit]
                part2gndlits = {part_with_f_lit: gndlits}
            if not isconj: # if we don't have a conjunction, ground the formula with the given variable assignment
                gndformula = formula.ground(self.mrf, var_assign)
            for partition, gndlits in part2gndlits.iteritems():
                # for each partition, select the ground atom truth assignments
                # in such a way that the conjunction is rendered true. There
                # is precisely one such assignment for each partition. (criterion 3/4)
                evidence = {}
                if isconj:
                    for gndlit in gndlits:
                        evidence[gndlit.gndAtom.idx] = 0 if gndlit.negated else 1
                for world in partition.generatePossibleWorldTuples(evidence):
                    # update the sufficient statistics for the given formula, partition and world value
                    worldidx = partition.getPossibleWorldIndex(world)
                    if isconj:
                        truth = 1
                    else:
                        # temporarily set the evidence in the MRF, compute the truth value of the 
                        # formula and remove the temp evidence
                        for atomIdx, value in partition.worldTuple2EvidenceDict(world).iteritems():
                            self.mrf._setTemporaryEvidence(atomIdx, value)
                        truth = gndformula.isTrue(self.mrf.evidence)
                        self.mrf._removeTemporaryEvidence()
                    if truth != 0:
                        self.partRelevantFormulas[partition.idx].add(formula.idxFormula)
                        self.addStatistics(formula.idxFormula, partition.idx, worldidx, partition.getNumberOfPossibleWorlds(), truth)
            return
            
        lit = literals[0]
        # ground the literal with the existing assignments
        gndlit = lit.ground(self.mrf, var_assign, allowPartialGroundings=True)
        for assign in Logic.iterEqVariableAssignments(gndlit, formula, self.mrf) if self.mrf.mln.logic.isEquality(gndlit) else gndlit.iterVariableAssignments(self.mrf):
            # copy the arguments to avoid side effects
            # if f_gndlit_parts is None: f_gndlit_parts = set()
            # else: f_gndlit_parts = set(f_gndlit_parts)
            if processed is None: processed = []
            else: processed = list(processed)
            # ground with the remaining free variables
            gnd_lit_ = gndlit.ground(self.mrf, assign)
            truth = gnd_lit_.isTrue(self.mrf.evidence)
            # treatment of equality constraints
            if isinstance(gnd_lit_, Logic.Equality):
                if isconj:
                    if truth == 1:
                        self._computeStatisticsRecursive(literals[1:], gndliterals, dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj)
                    else: continue
                else:
                    self._computeStatisticsRecursive(literals[1:], gndliterals + [gnd_lit_], dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj) 
                continue
            atomidx = gnd_lit_.gndAtom.idx

            if atomidx in processed: continue
            
            # if we encounter a gnd literal that is false by the evidence
            # and there is already a false one in this grounding from a different
            # partition, we can stop the grounding process here. The gnd conjunction
            # will never ever be rendered true by any of this partitions values (criterion no. 5)
            isEvidence = hasattr(self, 'queryPreds') and gnd_lit_.gndAtom.predName not in self.queryPreds
            assert isEvidence == False
            if isconj and truth == 0:
                falseLitInPart = False
                if f_gndlit_parts is not None and not f_gndlit_parts.contains(atomidx):
                    continue
                elif isEvidence: continue
                else:
                    self._computeStatisticsRecursive(literals[1:], gndliterals + [gnd_lit_], dict_union(var_assign, assign), formula, self.atomIdx2partition[atomidx], processed, isconj) 
                    continue
            elif isconj and isEvidence:
                self._computeStatisticsRecursive(literals[1:], gndliterals, dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj) 
                continue
                 
            self._computeStatisticsRecursive(literals[1:], gndliterals + [gnd_lit_], dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj) 
    

    @staticmethod
    def chain(variable):
        '''
        Returns a chained/flattened list of all gnd atom indices in the given variable
        '''
        atomIndices = []
        for v in variable:
            if type(v) is list:
                for a in v:
                    atomIndices.append(a)
            else:
                atomIndices.append(v)
        return atomIndices


    def _computeProbabilities(self, w):
        probs = {}#numpy.zeros(len(self.partitions))
        for partIdx in range(len(self.partitions)):
            sums = numpy.zeros(self.partValueCount[partIdx])
            for f in self.partRelevantFormulas[partIdx]:
                for i, v in enumerate(self.statistics[f][partIdx]):
                    val = v * w[f]
                    sums[i] += val
            sum_min = numpy.min(sums)
            sums -= sum_min
            sum_max = numpy.max(sums)
            sums -= sum_max
            expsums = numpy.sum(numpy.exp(sums))
            s = numpy.log(expsums)
            probs[partIdx] = numpy.exp(sums - s)
#             expsum = numpy.exp(sums)
#             probs[partIdx] = expsum / fsum(expsum)
        return probs
        

    def _f(self, w, **params):
        logger = logging.getLogger(self.__class__.__name__)
        if self.current_wts is None or not numpy.array_equal(self.current_wts, w):
            self.current_wts = w
            self.probs = self._computeProbabilities(w)
#         self.probs = self._computeProbabilities(w)
        likelihood = numpy.zeros(len(self.partitions))
        for partIdx in range(len(self.partitions)):
            p = self.probs[partIdx][self.evidenceIndices[partIdx]]
            if p == 0: p = 1e-10
            likelihood[partIdx] += p
        self.iter += 1
        return fsum(map(log, likelihood))
            
    def _grad(self, w, **params):    
        log = logging.getLogger(self.__class__.__name__)
        if self.current_wts is None or not numpy.array_equal(self.current_wts, w):
            self.current_wts = w
            self.probs = self._computeProbabilities(w)
        grad = numpy.zeros(len(w))
        for fIdx, partitions in self.statistics.iteritems():
            for part, values in partitions.iteritems():
                v = values[self.evidenceIndices[part]]
                for i, val in enumerate(values):
                    v -= self.probs[part][i] * val
                grad[fIdx] += v
        self.grad_opt_norm = float(sqrt(fsum(map(lambda x: x * x, grad))))
        return numpy.array(grad)
    
    
    class GndAtomPartition(object):
        '''
        Represents a partition of the PLL blocks in the MRF. Provides a couple
        of convencience methods.
        '''
        
        def __init__(self, mrf, atomicblocks, idx):
            self.variables = atomicblocks
            self.mrf = mrf
            self.idx = idx
            
            
        def contains(self, atom):
            '''
            Returns True iff the given ground atom or ground atom index is part of
            this partition.
            '''
            if isinstance(atom, Logic.GroundAtom):
                return self.contains(atom.idx)
            elif type(atom) is int:
                return atom in self.getGndAtomsPlain()
            else:
                raise Exception('Invalid type of atom: %s' % type(atom))
            
            
        def worldTuple2EvidenceDict(self, worldtuple):
            '''
            Takes a possible world tuple of the form ((0,),(0,),(1,0,0),(1,)) and transforms
            it into a dict mapping the respective atom indices to their truth values
            '''
            evidence = {}
            for block, value in zip(self.variables, worldtuple):
                evidence.update(block.worldTuple2EvidenceDict(value))
            return evidence
            
        
        def getEvidenceIndex(self, evidence=None):
            '''
            Returns the index of the possible world value of this partition that is represented
            by evidence. If evidence is None, the evidence set in the MRF is used.
            '''
            if evidence is None:
                evidence = self.mrf.evidence
            evidenceTuple = []
            for block in self.variables:
                evidenceTuple.append(block.getEvidenceValue(evidence))
            return self.getPossibleWorldIndex(tuple(evidenceTuple))
        
        
        def getPossibleWorldIndex(self, possible_world):
            '''
            Computes the index of the given possible world that would be assigned
            to it by recursively generating all worlds by iterPossibleWorlds().
            possible_world needs to by (nested) tuple of truth values.
            Exp: ((0,),(0,),(1,0,0),(0,)) --> 0
                 ((0,),(0,),(1,0,0),(1,)) --> 1
                 ((0,),(0,),(0,1,0),(0,)) --> 2
                 ((0,),(0,),(0,1,0),(1,)) --> 3
                 ...
            '''
            idx = 0
            for i, (block, val) in enumerate(zip(self.variables, possible_world)):
                exponential = 2 ** (len(self.variables) - i - 1)
                validx = block.getValueIndex(val)
                idx += validx * exponential
            return idx
                    
                
        def generatePossibleWorldTuples(self, evidence=None):
            '''
            Yields possible world values of this partition in the form
            ((0,),(0,),(1,0,0),(0,)), for instance. Nested tuples represent mutex variables.
            All tuples are consistent with the evidence at hand. Evidence is
            a dict mapping a ground atom index to its (binary) truth value.
            '''
            if evidence is None:
                evidence = []
            for world in self._generatePossibleWorldTuplesRecursive(self.variables, [], evidence):
                yield world
        
        
        def _generatePossibleWorldTuplesRecursive(self, atomicblocks, assignment, evidence):
            '''
            Recursively generates all tuples of possible worlds that are consistent
            with the evidence at hand.
            '''
            if len(atomicblocks) == 0:
                yield tuple(assignment)
                return
            block = atomicblocks[0]
            for val in block.generateValueTuples(evidence):
                for world in self._generatePossibleWorldTuplesRecursive(atomicblocks[1:], assignment + [val], evidence):
                    yield world
                        
            
        def getGndAtomsPlain(self):
            '''
            Returns a plain list of all ground atom indices in this partition.
            '''
            atomIndices = []
            for v in self.variables:
                atomIndices.extend(v.iteratoms())
            return atomIndices
        
        
        def getNumberOfPossibleWorlds(self):
            '''
            Returns the number of possible (partial) worlds of this partition
            '''
            count = 1
            for v in self.variables:
                count *= v.getNumberOfValues()
            return count
        
        
        def var2String(self, varIdx):
            return ','.join(map(str, self.variables[varIdx]))
        
                
        def __str__(self):
            s = []
            for v in self.variables:
                s.append(str(v))
            return '%d: [%s]' % (self.idx, ','.join(s))
    
    
#     def __printPartitions(self):
#         log = logging.getLogger(self.__class__.__name__)
#         for idx, p in enumerate(self.partitions):
#             log.info([self.mrf.gndAtomsByIdx[i] if type(i) is int else map(lambda x: str(self.mrf.gndAtomsByIdx[x]), i) for i in p])
#             for evidence in self._iterPartitionValues(idx):
#                 log.info('VALUE')
#                 for a in p:
#                     if type(a) is list:
#                         val = self.mrf.gndAtomsByIdx[a[[v for i, v in enumerate(evidence) if i in a].index(1)]]
#                         log.info('  %s = %.1f' % (val, 1.))
#                     else:
#                         log.info('  %s = %.1f' % (str(self.mrf.gndAtomsByIdx[a]), evidence[a]))
        

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
        self.atomicVariables = [block for block in self.mrf.gndAtomicBlocks.values() if block.predicate.predname in self.queryPreds]
    
    
GndAtomPartition = CLL.GndAtomPartition
