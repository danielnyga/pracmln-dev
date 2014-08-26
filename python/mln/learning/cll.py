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
        self.evidenceIndices = {}
        self.partValueCount = {}
        size = self.partSize
        while len(variables) > 0:
            vars = variables[:size if len(variables) > size else len(variables)]
            partVariables = map(lambda v: v[0] if v[0] is not None else v[1], vars)
            partidx = len(self.partitions)
            partition = CLL.GndAtomPartition(self.mrf, partVariables, partidx)
            # create the mapping from atoms to their partitions
            for atomIdx in partition.getGndAtomsPlain():
                self.atomIdx2partition[atomIdx] = partition
            log.debug('created partition: %s' % str(partition))
            self.partValueCount[partidx] = partition.getNumberOfPossibleWorlds()
            self.partitions.append(partition)
            self.evidenceIndices[partidx] = partition.getEvidenceIndex()
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
        gndlit = lit.ground(self.mrf, var_assign, allowPartialGroundings=len(gndliterals) == 0)
        for assign in Logic.iterEqVariableAssignments(gndlit, formula, self.mrf) if self.mrf.mln.logic.isEquality(gndlit) else gndlit.iterVariableAssignments(self.mrf):
            # copy the arguments to avoid side effects
            if f_gndlit_parts is None: f_gndlit_parts = []
            else: f_gndlit_parts = list(f_gndlit_parts)
            if processed is None: processed = []
            else: processed = list(processed)
            # ground with the remaining free variables
            gnd_lit_ = gndlit.ground(self.mrf, assign)
            truth = gnd_lit_.isTrue(self.mrf.evidence)
            # treatment of equality constraints
            if isinstance(gnd_lit_, Logic.Equality):
                if truth == 1 or not isconj:
                    self._computeStatisticsRecursive(literals[1:], gndliterals, dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj)
                continue
            atomidx = gndlit.gndAtom.idx
            if atomidx in processed: continue
            
            # if we encounter a gnd literal that is false by the evidence
            # and there is already a false one in this grounding from a different
            # partition, we can stop the grounding process here. The gnd conjunction
            # will never ever be rendered true by any of this partitions values (criterion no. 5)
            if isconj and truth == 0:
                if len(f_gndlit_parts) > 0 and not any(map(lambda p: p.contains(atomidx), f_gndlit_parts)): continue
                else: f_gndlit_parts.append(self.atomIdx2partition[atomidx])
                 
            self._computeStatisticsRecursive(literals[1:], gndliterals + [gnd_lit_], dict_union(var_assign, assign), formula, f_gndlit_parts, processed, isconj) 
    

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


#     def _getBlockProbMB(self, idxVar, wt):        
#         (idxGA, block) = self.mrf.pllBlocks[idxVar]
#         numValues = 2 if idxGA is not None else len(block)
#         
#         relevantFormulas = self.blockRelevantFormulas.get(idxVar, None)
#         if relevantFormulas is None: # no list was saved, so the truth of all formulas is unaffected by the variable's value
#             # uniform distribution applies
#             p = 1.0 / numValues
#             return [p] * numValues
#         
#         sums = numpy.zeros(numValues)
#         for idxFormula in relevantFormulas:
#             for idxValue, n in enumerate(self.fcounts[idxFormula][idxVar]):
#                 sums[idxValue] += n * wt[idxFormula]
#         sum_min = numpy.min(sums)
#         sums -= sum_min
#         sum_max = numpy.max(sums)
#         sums -= sum_max
#         expsums = numpy.sum(numpy.exp(sums))
#         s = numpy.log(expsums)
#         return numpy.exp(sums - s)

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
        
        def __init__(self, mrf, variables, idx):
            self.variables = variables
            self.mrf = mrf
            self.idx = idx
            
            
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
            Raises an exception if atomidx is not at all contained in this partition.
            '''
            for v in self.variables:
                if type(v) is list:
                    for a in v:
                        if a == atomidx: return v
                else:
                    None
            raise Exception('Ground atom %s is not in the partition %s' % (str(self.mrf.gndAtomsByIdx[atomidx]), str(self)))
        
        
        def worldTuple2EvidenceDict(self, worldtuple):
            '''
            Takes a possible world tuple of the form (0,0,(1,0,0),1) and transforms
            it into a dict mapping the respective atom indices to their truth values
            '''
            evidence = {}
            for variable, value in zip(self.variables, worldtuple):
                if type(variable) is list:
                    for var_, val_ in zip(variable, value):
                        evidence[var_] = val_
                else:
                    evidence[variable] = value
            return evidence
            
        
        def getEvidenceIndex(self, evidence=None):
            '''
            Returns the index of the possible world value of this partition that is represented
            by evidence. If evidence is None, the evidence set in the MRF is used.
            '''
            if evidence is None:
                evidence = self.mrf.evidence
            evidenceTuple = []
            for variable in self.variables:
                if type(variable) is list:
                    evidenceTuple.append(tuple([evidence[atom] for atom in variable]))
                else:
                    evidenceTuple.append(evidence[variable])
            return self.getPossibleWorldIndex(evidenceTuple)
        
        
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
            Nested tuples represent mutex variables. 
            '''
            idx = 0
            for i, (_, val) in enumerate(zip(self.variables, possible_world)):
                exponential = 2 ** (len(self.variables) - i - 1)
                if type(val) is tuple:
                    idx += val.index(1.) * exponential 
                else:
                    idx += int(val) * exponential
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
            
            
        def generatePossibleWorldTuples(self, evidence=None):
            '''
            Yields possible world values of this partition in the form
            (0,0,(1,0,0),0), for instance. Nested tuples represent mutex variables.
            All tuples are consistent with the evidence at hand. Evidence is
            a dict mapping a ground atom index to its (binary) truth value.
            '''
            if evidence is None:
                evidence = []
            for world in self._generatePossibleWorldTuplesRecursive(self.variables, [], evidence):
                yield world
        
        
        def _generatePossibleWorldTuplesRecursive(self, variables, assignment, evidence):
            '''
            Recursively generates all tuples of possible worlds that are consistent
            with the evidence at hand.
            '''
            if len(variables) == 0:
                yield tuple(assignment)
                return
            
            variable = variables[0]
            if type(variable) is list: # a mutex variable
                valpattern = []
                for mutexatom in variable:
                    valpattern.append(evidence.get(mutexatom, None))
                # at this point, we have generated a value pattern with
                # all values that are fixed by the evidence argument and None
                # for all others
                trues = sum(filter(lambda x: x == 1, valpattern))
                if trues > 1: # sanity check
                    raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
                if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
                    for world in self._generatePossibleWorldTuplesRecursive(variables[1:], assignment + [tuple(map(lambda x: 1 if x == 1 else 0, valpattern))], evidence):
                        yield world
                for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
                    if val == 0: continue
                    elif val is None:
                        values = [0] * len(valpattern)
                        values[i] = 1
                        for world in self._generatePossibleWorldTuplesRecursive(variables[1:], assignment + [tuple(values)], evidence):
                            yield world
            else: # a regular ground atom
                values = [0, 1]
                if variable in evidence: # this atom is fixed by evidence
                    values = [evidence[variable]]
                for value in values:
                    for world in self._generatePossibleWorldTuplesRecursive(variables[1:], assignment + [value], evidence):
                        yield world
                        
            
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
        self.atomicVariables = filter(lambda block: self._getPredNameForPllBlock(block) in self.queryPreds, self.mrf.pllBlocks)
    
    
    
