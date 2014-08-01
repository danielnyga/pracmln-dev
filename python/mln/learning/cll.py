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
from utils import dict_union

class CLL(AbstractLearner):
    '''
    Implementation of composite-log-likelihood learning.
    '''
    
    groundingMethod = 'NoGroundingFactory'
    
    def __init__(self, mln, mrf=None, **params):
        AbstractLearner.__init__(self, mln, mrf, **params)
        self.partSize = params.get('partSize', 1)
        self.partitions = []
        self.mrf._getPllBlocks()
        self.statistics = {}
        self.partRelevantFormulas = defaultdict(set)
        self.evidenceIndices = {} # maps partition idx to index of value given by evidence
        self.partValueCount = {}
        self.atomIdx2partition = {} # maps a gnd atom index to its comprising partition
        
                
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
        self.atomicVariables = list(self.mrf.pllBlocks)
        
        
    def _prepareOpt(self):
        log = logging.getLogger(self.__class__.__name__)
        # create random partition of the ground atoms
        self._createVariables()
        variables = self.atomicVariables
        random.shuffle(variables)
        self.partitions = []
        self.atomIdx2partition = {}
        size = self.partSize
        while len(variables) > 0:
            vars = variables[:size if len(variables) > size else len(variables)]
            partVariables = map(lambda v: v[0] if v[0] is not None else v[1], vars)
            partition = CLL.GndAtomPartition(self.mrf, partVariables)
            # create the mapping from atoms to their partitions
            for atomIdx in partition.getGndAtomsPlain():
                self.atomIdx2partition[atomIdx] = partition
            log.debug('created partition: %s' % str(partition))
            self.partitions.append(partition)
            variables = variables[len(partition.variables):]
        log.debug('CLL created %d partitions' % len(self.partitions))
        self._computeStatistics()
        
        
    def run(self, **params):
        '''
        This is a modification of the run method of the AbstractLearner, which
        runs the optimization only for a specified number of iterations and
        then reconfigures the CLL partitions.
        initialWts: whether to use the MLN's current weights as the starting point for the optimization
        '''
        
        log = logging.getLogger(self.__class__.__name__)
        if not 'scipy' in sys.modules:
            raise Exception("Scipy was not imported! Install numpy and scipy if you want to use weight learning.")
        # initial parameter vector: all zeros or weights from formulas
        wt = numpy.zeros(len(self.mln.formulas), numpy.float64)
        if self.initialWts:
            for i in range(len(self.mln.formulas)):
                wt[i] = self.mln.formulas[i].weight
            log.debug('Using initial weight vector: %s' % str(wt))
                
        # precompute fixed formula weights
        self._fixFormulaWeights()
        self.wt = self._projectVectorToNonFixedWeightIndices(wt)
        
        self.params.update(params)
        repart = self.params.get('maxrepart', 5)
        for i in range(repart):
            self._prepareOpt()
            self._optimize(**params)
            self._postProcess()
            
        return self.wt
    
            
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
        pass
    
    
    def _comp_conj_stat(self, conj, gndconj, var_assign, f_gndlit_parts=None, processed=None):
        '''
        TODO: make sure that there are no equality constraints in the conjunction!
        '''
        if len(conj) == 0:
            # at this point, we have fully grounded conjunction in gndconj
            # create a mapping from a partition to the ground literals in this conjunction
            # (criterion no. 1)
            part2gndlits = defaultdict(list)
            part_with_f_lit = None
            for gndlit in gndconj:
                part = self.atomIdx2partition[gndlit.gndAtom.idx]
                part2gndlits[part].append(gndlit)
                if gndlit.isTrue(self.mrf.evidence) == 0:
                    part_with_f_lit = part  
            # if there is a false ground literal we only need to take into account
            # the partition comprising this literal (criterion no. 2)
            # there is maximally one such partition with false literals in the conjunction
            # because of criterion no. 5
            if part_with_f_lit is not None:
                gndlits = part2gndlits[part_with_f_lit]
                part2gndlits = {}
                part2gndlits[part] = gndlits 
            
            for partition, gndlits in part2gndlits.iteritems():
                pass
                
            
        lit = conj[0]
        if f_gndlit_parts is None: f_gndlit_parts = []
        if processed is None: processed = []
        # ground the literal with the existing assignments
        gndlit = lit.ground(self.mrf, var_assign)
        for assign in gndlit.iterVariableAssignments(self.mrf):
            # ground with the remaining free variables
            gnd_lit_ = lit.ground(self.mrf, assign)
            truth = gndlit.isTrue(self.mrf.evidence)
            atomidx = gndlit.gndAtom.idx
            if atomidx in processed: continue
            
            # if we encounter a gnd literal that is false by the evidence
            # and there is already a false one in this grounding from a different
            # partition, we can stop the grounding process here. The gnd conjunction
            # will never ever be rendered true by any of the partitions (criterion no. 5)
            if truth == 0:
                if len(f_gndlit_parts) > 0 and not any(map(lambda p: p.contains(atomidx), f_gndlit_parts)): continue
                else: f_gndlit_parts.append(self.atomIdx2partition[atomidx])
                 
            self._comp_conj_stat(conj[1:], gndconj + [gnd_lit_], dict_union(var_assign, assign), f_gndlit_parts) 
        
        

#     def _computeStatistics(self):
#         log = logging.getLogger(self.__class__.__name__)
#         log.info('Computing statistics...')
#         self.statistics = {} # maps formula index to a dict of variables
#         # collect for each partition the set of relevant ground formulas
#         evidenceBackup = list(self.mrf.evidence)
#         for partIdx, partition in enumerate(self.partitions):
#             # remove the evidence of the partition variables temporarily
#             self.partValueCount[partIdx] = partition.getNumberOfPossibleWorlds()
#             atomIndices = partition.getGndAtomsPlain()
#             for atomIdx in atomIndices:
#                 self.mrf._setTemporaryEvidence(atomIdx, None)
#             self.partRelevantFormulas[partIdx] = set()
#             for gf in self._iterFormulaGroundingsForVariable(): # generates all relevant ground formulas for the current partition
#                 if set(atomIndices).isdisjoint(gf.idxGroundAtoms()):
#                     continue
#                 for valIdx, val in enumerate(partition.iterPossibleWorlds(evidenceBackup)):
#                     if val == evidenceBackup:
#                         self.evidenceIndices[partIdx] = valIdx
#                     truth = gf.isTrue(val)
#                     self.addStatistics(gf.fIdx, partIdx, valIdx, self.partValueCount[partIdx], truth)
#                 self.partRelevantFormulas[partIdx].add(gf.fIdx)
#             # collect the evidence value index of the partition (the value that holds in the evidence)
#             if partIdx not in self.evidenceIndices:
#                 for valIdx, val in enumerate(partition.iterPossibleWorlds(evidenceBackup)):
#                     if val == evidenceBackup:
#                         self.evidenceIndices[partIdx] = valIdx
#             if not partIdx in self.evidenceIndices:
#                 raise Exception('No admissible partition value found specified in evidence. Missing a functional constraint?')
#             # re-assert the evidence
#             self.mrf._removeTemporaryEvidence()

    
    def _iterFormulaGroundingsForVariable(self):
        '''
        Make sure that you have set temporary evidence for the 
        ground atoms in the variable to None before calling this method
        and to remove it afterwards
        '''
        formulas = []
        for i, f in enumerate(self.mrf.formulas):
            f_ = f.ground(self.mrf, {}, allowPartialGroundings=True, simplify=True)
            if isinstance(f_, Logic.TrueFalse):
                continue
            f_.weight = f.weight
            f_.isHard = f.isHard
            f_.fIdx = i
            formulas.append(f_)
        for formula in formulas:
            for groundFormula in self._groundAndSimplifyFormula(formula, formula.getVariables(self.mrf.mln)):
                yield groundFormula
        
    def _groundAndSimplifyFormula(self, formula, domains):
        if len(domains) == 0:
            yield formula
            return
        domains = dict(domains)
        for variable, domain_name in domains.iteritems(): break
        del domains[variable]
        domain = self.mrf.domains[domain_name]
        for value in domain:
            partialGrounding = formula.ground(self.mrf, {variable: value}, allowPartialGroundings=True, simplify=True)
            if isinstance(partialGrounding, Logic.TrueFalse):
                continue
            partialGrounding.fIdx = formula.fIdx
            partialGrounding.weight = formula.weight
            for fg in self._groundAndSimplifyFormula(partialGrounding, domains):
                yield fg
        
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
#             sum_min = numpy.min(sums)
#             sums -= sum_min
#             sum_max = numpy.max(sums)
#             sums -= sum_max
#             expsums = numpy.sum(numpy.exp(sums))
#             s = numpy.log(expsums)
#             probs[partIdx] = numpy.exp(sums - s)
            expsum = numpy.exp(sums)
            probs[partIdx] = expsum / fsum(expsum)
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
        grad = numpy.zeros(len(w))
        for fIdx, partitions in self.statistics.iteritems():
            for part, values in partitions.iteritems():
                v = values[self.evidenceIndices[part]]
                for i, val in enumerate(values):
                    v -= probs[part][i] * val
                grad[fIdx] += v
        self.grad_opt_norm = float(sqrt(fsum(map(lambda x: x * x, grad))))
        return numpy.array(grad)
    
    
    class GndAtomPartition(object):
        '''
        Represents a partition of the PLL blocks in the MRF. Provides a couple
        of convencience methods.
        '''
        
        def __init__(self, mrf, variables):
            self.variables = variables
            self.mrf = mrf
            
            
        def _setEvidence(self, evidence, gndAtomIdx, truth):
            '''
            Sets the truth value of the given gndAtomIdx in evidence to truth.
            Takes into account mutex constraints, i.e. sets all other gndAtoms
            in the respective block to truth=0. For such atoms, the truth value 
            can only be set to 1.0.
            '''
            if truth is None:
                raise Exception('Truth must not be None in _setEvidence(). In order to set evidence to None, use _eraseEvidence()')
            if gndAtomIdx in self.mrf.gndBlockLookup:
                if truth != 1.:
                    raise Exception('Cannot set a mutex variable to truth value %s' % str(truth))
                blockName = self.mrf.gndBlockLookup[gndAtomIdx]
                atomIdxInBlock = self.mrf.gndBlocks[blockName]
                for idx in atomIdxInBlock:
                    evidence[idx] = .0 if idx != gndAtomIdx else 1.
            else:
                evidence[gndAtomIdx] = truth
                
                
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
            
            
        def getMutexBlock(self, atomidx):
            '''
            Returns the list of ground atom indices that are with
            atomidx in the same mutex var, or None if atomidx is not a mutex var.
            Raises an exception if atomidx is not at contained in this partition.
            '''
            for v in self.variables:
                if type(v) is list:
                    for a in v:
                        if a == atomidx: return v
                else:
                    None
            raise Exception('Ground atom %s is not in the partition %s' % (str(self.mrf.gndAtomsByIdx[atomidx]), str(self)))
        
        
        def getPossibleWorldIndex(self, possible_world):
            '''
            Computes the index of the given possible world that would be assigned
            to it by recursively generating all worlds by iterPossibleWorlds().
            possible_world needs to by (nested) tuple of truth values.
            Exp: (0,0,(1,0,0),0) --> 0
                 (0,0,(1,0,0),1) --> 1
                 (0,0,(0,1,0),0) --> 2
                 (0,0,(0,1,0),1) --> 3
                 ...
                 nested tuples represent mutex variables. 
            '''
            idx = 0
            for i, (_, val) in enumerate(zip(self.variables, possible_world)):
                exponential = 2 ** (len(self.variables) - i - 1)
                if type(val) is list:
                    idx += val.index(1.) * exponential 
                else:
                    idx += val * exponential
            return idx
                    
                
        def _eraseEvidence(self, evidence, gndAtomIdx):
            '''
            Deletes the evidence of the given gndAtom, i.e. set its truth in evidence to None.
            if the given gndAtom is part of a mutex constraint, the whole block is set to None.
            '''
            if gndAtomIdx in self.mrf.gndBlockLookup:
                blockName = self.mrf.gndBlockLookup[gndAtomIdx]
                atomIdxInBlock = self.mrf.gndBlocks[blockName]
                for idx in atomIdxInBlock:
                    evidence[idx] = None
            else:
                evidence[gndAtomIdx] = None
            
        
        def iterPossibleWorlds(self, evidence):
            '''
            Yields possible worlds (truth values) of this partition for all 
            ground atoms in the MRF, where the gndAtoms values of this partition
            are set accordingly to their possible values.
            '''
            for value in self._iterPartitionValuesRec(self.variables, evidence):
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
                    self._setEvidence(evidence, atom, 1.0)
                    for ev in self._iterPartitionValuesRec(variables[1:], evidence):
                        yield ev
            else:
                for truth in (evidence[variable], 1. - evidence[variable]):
                    self._setEvidence(evidence, variable, truth)
                    for ev in self._iterPartitionValuesRec(variables[1:], evidence):
                        yield ev
                        
                        
        def getGndAtomsPlain(self):
            '''
            Returns a plain list of all ground atom indices in this partition.
            '''
            atomIndices = []
            for v in self.variables:
                if type(v) is list:
                    for a in v: atomIndices.append(a)
                else: atomIndices.append(v)
            return atomIndices
        
        
        def getNumberOfPossibleWorlds(self):
            '''
            Returns the number of possible (partial) worlds of this partition
            '''
            count = 1
            for v in self.variables:
                if type(v) is list: count *= len(v)
                else: count *= 2
            return count
        
        
        def __str__(self):
            s = []
            for v in self.variables:
                if type(v) is list: s.append('[%s]' % (','.join(map(str, map(lambda a: self.mrf.gndAtomsByIdx[a], v)))))
                else: s.append(str(self.mrf.gndAtomsByIdx[v]))
            return '[%s]' % ','.join(s)
    
    
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
        self.atomicVariables = filter(lambda block: self._getPredNameForPllBlock(block) in self.queryPreds, self.mrf.pllBlocks)
    
    
    
