# Markov Logic Networks - Grounding
#
# (C) 2013 by Daniel Nyga (nyga@cs.tum.edu)
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

from collections import defaultdict
# from logic.fol import isConjunctionOfLiterals
from utils.undo import Ref, Number, List, ListDict, Boolean
import utils
from mln.grounding.default import DefaultGroundingFactory
from mln.learning.common import AbstractLearner
from debug import DEBUG
from utils import combinations
from mln.util import strFormula
import math
from logic.common import Logic
import sys
import logging


class FormulaGrounding(object):
    '''
    Represents a particular (partial) grounding of a formula with respect to _one_ predicate
    and in terms of disjoint sets of variables occurring in that formula. A grounding of
    the formula is represented as a list of assignments of the independent variable sets.
    It represents a node in the search tree for weighted SAT solving.
    Additional fields:
    - depth:    the depth of this formula grounding (node) in the search tree
                The root node (the formula with no grounded variable has depth 0.
    - children: list of formula groundings that have been generated from this fg.
    ''' 

    def __init__(self, formula, mrf, parent=None, assignment=None):
        '''
        Instantiates the formula grounding for a given
        - formula:    the formula grounded in this node
        - mrf:        the MRF associated to this problem
        - parent:     the formula grounding this fg has been created from
        - assignment: dictionary mapping variables to their values
        '''
        self.mrf = mrf
        self.formula = formula
        self.parent = Ref(parent)
        self.trueGroundings = Number(0.)
        self.processed = Boolean(False)
        if parent is None:
            self.depth = 0
        else:
            self.depth = parent.depth + 1
        self.children = List()
        self.assignment = assignment
        self.domains = ListDict()
        if parent is None:
            for var in self.formula.getVariables(self.mrf.mln):
                self.domains.extend(var, list(self.mrf.domains[self.formula.getVarDomain(var, self.mrf.mln)]))
        else:
            for (v, d) in parent.domains.iteritems():
                self.domains.extend(v, list(d))
        self.domains.epochEndsHere()
                
    def epochEndsHere(self):
        for mem in (self.parent, self.trueGroundings, self.children, self.domains, self.processed):
            mem.epochEndsHere()
        
    def undoEpoch(self):
        for mem in (self.parent, self.trueGroundings, self.children, self.domains, self.processed):
            mem.undoEpoch()
            
    def countGroundings(self):
        '''
        Computes the number of ground formulas subsumed by this FormulaGrounding
        based on the domain sizes of the free (unbound) variables.
        '''
        gf_count = 1
        for var in self.formula.getVariables(self.mrf):
            domain = self.mrf.domains[self.formula.getVarDomain(var, self.mrf)]
            gf_count *= len(domain)
        return gf_count
    
    def ground(self, assignment=None):
        '''
        Takes an assignment of _one_ particular variable and
        returns a new FormulaGrounding with that assignment. If
        the assignment renders the formula false true, then
        the number of groundings rendered true is returned.
        '''
        # calculate the number of ground formulas resulting from
        # the remaining set of free variables
        if assignment is None:
            assignment = {}
        gf_count = 1
        for var in set(self.formula.getVariables(self.mrf.mln)).difference(assignment.keys()):
            domain = self.domains[var]
            if domain is None: return 0.
            gf_count *= len(domain)
        gf = self.formula.ground(self.mrf, assignment, allowPartialGroundings=True)
        gf.weight = self.formula.weight
        for var_name, val in assignment.iteritems(): break
        self.domains.drop(var_name, val)
        # if the simplified gf reduces to a TrueFalse instance, then
        # we return the no of groundings if it's true, or 0 otherwise.
        truth = gf.isTrue(self.mrf.evidence)
        if truth in (True, False):
            if not truth: trueGFCounter = 0.0
            else: trueGFCounter = gf_count
            self.trueGroundings += trueGFCounter
            return trueGFCounter
        # if the truth value cannot be determined yet, we return
        # a new formula grounding with the given assignment
        else:
            new_grounding = FormulaGrounding(gf, self.mrf, parent=self, assignment=assignment)
            self.children.append(new_grounding)
            return new_grounding
        
    def __str__(self):
        return str(self.assignment) + '->' + str(self.formula) + str(self.domains)#str(self.assignment)
    
    def __repr__(self):
        return str(self)


class SmartGroundingFactory(object):
    '''
    Implements a factory for generating the groundings of one formula. 
    The groundings are created incrementally with one
    particular ground atom being presented at a time.
    fields:
    - formula:    the (ungrounded) formula representing the root of the
                  search tree
    - mrf:        the respective MRF
    - root:       a FormulaGrounding instance representing the root of the tree,
                  i.e. an ungrounded formula
    - costs:      the costs accumulated so far
    - depth2fgs:   mapping from a depth of the search tree to the corresponding list 
                  of FormulaGroundings
    - vars_processed:     list of variable names that have already been processed so far
    - values_processed:   mapping from a variable name to the list of values of that vaiable that
                          have already been assigned so far.
    This class maintains a stack of all its fields in order allow undoing groundings
    that have been performed once.
    '''
    
    def __init__(self, formula, mrf):
        '''
        formula might be a formula or a FormulaGrounding instance.
        '''
        self.mrf = mrf
        self.costs = .0
        if isinstance(formula, Logic.Formula):
            self.formula = formula
            self.root = FormulaGrounding(formula, mrf)
        elif isinstance(formula, FormulaGrounding):
            self.root = formula
            self.formula = formula.formula
        self.values_processed = ListDict()
        self.variable_stack = List(None)
        self.var2fgs = ListDict({None: [self.root]})
        self.gndAtom2fgs = ListDict()
        self.manipulatedFgs = List()
    
    def epochEndsHere(self):
        for mem in (self.values_processed, self.variable_stack, self.var2fgs, self.gndAtom2fgs, self.manipulatedFgs):
            mem.epochEndsHere()
        for fg in self.manipulatedFgs:
            fg.epochEndsHere()
            
    def undoEpoch(self):
        for fg in self.manipulatedFgs:
            fg.undoEpoch()
        for mem in (self.values_processed, self.variable_stack, self.var2fgs, self.gndAtom2fgs, self.manipulatedFgs):
            mem.undoEpoch()
        
    def ground(self, gndAtom):
        '''
        Expects a ground atom and creates all groundings 
        that can be derived by it in terms of FormulaGroundings.
        '''
        self.manipulatedFgs.clear()
        # get all variable assignments of matching literals in the formula 
        var_assignments = {}
        for lit in self.formula.iterLiterals():
            assignment = self.gndAtom2Assignment(lit, gndAtom)
            if assignment is not None:
                utils.unifyDicts(var_assignments, assignment)
        cost = .0
        
        # first evaluate formula groundings that contain 
        # this gnd atom as an artifact
        min_depth = None
        min_depth_fgs = []
        for fg in self.gndAtom2fgs.get(gndAtom, []):
            if len(self.variable_stack) <= fg.depth:
                continue
            if fg.processed.value:
                continue
            truth = fg.formula.isTrue(self.mrf.evidence)
            if truth is not None:
                cost -= fg.trueGroundings.value
                if not fg in self.manipulatedFgs:
                    self.manipulatedFgs.append(fg)
                fg.processed.set(True)
                self.var2fgs.drop(self.variable_stack[fg.depth], fg)
                if not fg.parent.obj in self.manipulatedFgs:
                    self.manipulatedFgs.append(fg.parent.obj)
                fg.parent.obj.children.remove(fg) # this is just for the visualization/ no real functionality
                if fg.depth == min_depth or min_depth is None:
                    min_depth_fgs.append(fg)
                    min_depth = fg.depth
                if fg.depth < min_depth:
                    min_depth = fg.depth
                    min_depth_fgs = []
                    min_depth_fgs.append(fg)
        for fg in min_depth_fgs:
            # add the costs which are aggregated by the root of the subtree 
            if fg.formula.isTrue(fg.mrf.evidence) == False:
                cost += fg.formula.weight * fg.countGroundings()
                fg.trueGroundings.set(cost)
        # straighten up the variable stack and formula groundings
        # since they might have become empty
        for var in list(self.variable_stack):
            if self.var2fgs[var] is None:
                self.variable_stack.remove(var)
        for var, value in var_assignments.iteritems():
            # skip the variables with values that have already been processed
            if not var in self.variable_stack:
                depth = len(self.variable_stack)
            else:
                depth = self.variable_stack.index(var)
            queue = list(self.var2fgs[self.variable_stack[depth - 1]])
            while len(queue) > 0:
                fg = queue.pop()
                # first hinge the new variable grounding to all possible parents,
                # i.e. all FormulaGroundings with depth - 1...
                if fg.depth < depth:
                    vars_and_values = [{var: value}]
                # ...then hinge all previously seen subtrees to the newly created formula groundings...    
                elif fg.depth >= depth and fg.depth < len(self.variable_stack) - 1:
                    vars_and_values = [{self.variable_stack[fg.depth + 1]: v} 
                                   for v in self.values_processed[self.variable_stack[fg.depth + 1]]]
                # ...and finally all variable values that are not part of the subtrees
                # i.e. variables that are currently NOT in the variable_stack
                # (since they have been removed due to falsity of a formula grounding).
                else:
                    vars_and_values = []
                    varNotInTree = None
                    for varNotInTree in [v for v in self.values_processed.keys() if v not in self.variable_stack]: break
                    if varNotInTree is None: continue
                    values = self.values_processed[varNotInTree]
                    for v in values:
                        vars_and_values.append({varNotInTree: v})
                for var_value in vars_and_values:
                    for var_name, val in var_value.iteritems(): break
                    if not fg.domains.contains(var_name, val): continue
                    gnd_result = fg.ground(var_value)
                    if not fg in self.manipulatedFgs:
                        self.manipulatedFgs.append(fg)
                    # if the truth value of a grounding cannot be determined...
                    if isinstance(gnd_result, FormulaGrounding):
                        # collect all ground atoms that have been created as 
                        # as artifacts for future evaluation
                        artifactGndAtoms = [a for a in gnd_result.formula.getGroundAtoms() if not a == gndAtom]
                        for artGndAtom in artifactGndAtoms:
                            self.gndAtom2fgs.put(artGndAtom, gnd_result)
                        if not var_name in self.variable_stack:
                            self.variable_stack.append(var_name)
                        self.var2fgs.put(self.variable_stack[gnd_result.depth], gnd_result)
                        queue.append(gnd_result)
                    else: # ...otherwise it's true/false; add its costs and discard it.
                        if self.formula.isHard and gnd_result > 0.:
                            gnd_result = float('inf')
                        cost += gnd_result
            self.values_processed.put(var, value)
        return cost
    
    def printTree(self):
        queue = [self.root]
        print '---'
        while len(queue) > 0:
            n = queue.pop()
            space = ''
            for _ in range(n.depth): space += '--'
            print space + str(n)
            queue.extend(n.children.list)
        print '---'
        
    def gndAtom2Assignment(self, lit, atom):
        '''
        Returns None if the literal and the atom do not match.
        '''
        if type(lit) is Logic.Equality or lit.predName != atom.predName: return None
        assignment = {}
        for p1, p2 in zip(lit.params, atom.params):
            if self.mrf.mln.logic.isVar(p1):
                assignment[p1] = p2
            elif p1 != p2: return None
        return assignment


class BPLLGroundingFactory(DefaultGroundingFactory):
    '''
    Grounding factory for efficient grounding for pseudo-likelihood
    learning. Treats conjunctions in linear time by exploitation
    of their semantics. Groundings for BPLL can be constructed directly.
    '''
    
    def __init__(self, mrf, db, **params):
        DefaultGroundingFactory.__init__(self, mrf, db, **params)
        self.mrf = mrf
        self.vars = []
        self.varIdx2GndAtom = {}
        self.gndAtom2VarIndex = {}
        self.varEvidence = {}
        self.blockVars = set()
        self.fcounts = {} 
        self.blockRelevantFormulas = defaultdict(set)
        
    def createVariablesAndEvidence(self):
        '''
        Create the variables, one binary for each ground atom.
        Considers also mutually exclusive blocks of ground atoms.
        '''
        self.evidenceIndices = []
        for (idxGA, block) in self.mrf.pllBlocks:
            if idxGA is not None:
                self.evidenceIndices.append(0)
            else:
                # find out which ga is true in the block
                idxValueTrueone = -1
                for idxValue, idxGA in enumerate(block):
                    truth = self.mrf._getEvidence(idxGA)
                    if truth > 0 and truth < 1:
                        raise Exception('Block variables must not have fuzzy truth values: %s in block "%s".' % (str(self.mrf.gndAtomsByIdx[idxGA]), str(block)))
                    if truth:
                        if idxValueTrueone != -1: 
                            raise Exception("More than one true ground atom in block '%s'!" % self.mrf._strBlock(block))
                        idxValueTrueone = idxValue
                if idxValueTrueone == -1: raise Exception("No true ground atom in block '%s'!" % self.mrf._strBlock(block))
                self.evidenceIndices.append(idxValueTrueone)
        self.trueGroundingsCounter = {}
        if DEBUG:
            print 'variables in smart grounding:'
            for i, var in enumerate(self.mrf.pllBlocks):
                print i, var, self.evidenceIndices[i]
    
    def _addMBCount(self, idxVar, size, idxValue, idxWeight,inc=1):
        self.blockRelevantFormulas[idxVar].add(idxWeight)
        if idxWeight not in self.fcounts:
            self.fcounts[idxWeight] = {}
        d = self.fcounts[idxWeight]
        if idxVar not in d:
            d[idxVar] = [0] * size
        d[idxVar][idxValue] += inc
        
    def _createGroundFormulas(self): pass
    
    def litIterGnd(self, mrf, lit):
        '''
        Iterate over all groundings of the given literal.
        Yields the grounding itself and the respective variable assignments.
        '''
        vars2doms = lit.getVariables(mrf)
        vars = vars2doms.keys()
        domains = [mrf.domains[vars2doms[v]] for v in vars]
        if len(domains) == 0:
            yield lit.ground(mrf, {}), {}
            return
        for c in combinations(domains):
            assignment = dict([(v,a) for v,a in zip(vars,c)])
            yield lit.ground(mrf, assignment, allowPartialGroundings=True), assignment
    
    def generateTrueConjunctionGroundings(self, fIdx, formula, conjunctsSoFar, minTruthLit=None, sndMinTruth=None):
        '''
        Recursively generate the true groundings of a conjunction and
        collect the statistics for pseudo-likelihood learning.
        '''
#         log = logging.getLogger('bpll')
#         log.debug(str(formula) + ' CONJ: ' + str(map(str, conjunctsSoFar)))
#         if minTruthLit is not None:
#             log.debug('minTruthLits: ' + str(map(str, minTruthLit)))
#             log.debug('minTruthLit: %.2f' % self.mrf.evidence[minTruthLit[0].gndAtom.idx])

        if formula is None:
            minTruth = self.mrf.evidence[minTruthLit[0].gndAtom.idx]
            for conj in conjunctsSoFar:
                truth = self.mrf.evidence[conj.gndAtom.idx]
                invMinTruth = min(1 - truth, minTruth)
                if conj in minTruthLit:
                    if len(minTruthLit) == 1 and sndMinTruth is not None:
                        invMinTruth = min(1 - minTruth, sndMinTruth)
                idxVar = self.mrf.atom2BlockIdx[conj.gndAtom.idx]
                (idxGA, block) = self.mrf.pllBlocks[idxVar]
                if idxGA is not None:
                    self._addMBCount(idxVar, 2, 0, fIdx, inc=minTruth)
                    self._addMBCount(idxVar, 2, 1, fIdx, inc=invMinTruth)
                else:
                    idxGATrueOne = block[self.evidenceIndices[idxVar]]
                    if conj.gndAtom.idx == idxGATrueOne and conj.negated is False:
                        self._addMBCount(idxVar, len(block), self.mrf.atom2ValueIdx[conj.gndAtom.idx], fIdx, inc=minTruth)

            return
        # remove the true equality constraints
        conjuncts = list(formula.children)
        eqConstraints = []
        while len(conjuncts) > 0 and isinstance(conjuncts[0], Logic.Equality):
            eq = conjuncts[0]
#             log.debug('  %s = %.2f' % (str(eq), eq.isTrue()))
            if eq.isTrue() == 0: 
                return
            elif eq.isTrue() is None: eqConstraints.append(eq)
            conjuncts = conjuncts[1:]
        
        if len(conjuncts) >= 1:
            conj = conjuncts[0]
            for gndLit, varAssign in self.litIterGnd(self.mrf, conj):
                gndLitTruth = gndLit.isTrue(self.mrf.evidence)
                sndMinTruth_ = sndMinTruth
                if minTruthLit is not None:
                    minTruthLit_ = list(minTruthLit)
                if minTruthLit is None:
                    minTruthLit_ = [gndLit]
                elif gndLitTruth < self.mrf.evidence[minTruthLit_[0].gndAtom.idx]:
                    sndMinTruth_ = self.mrf.evidence[minTruthLit_[0].gndAtom.idx]
                    minTruthLit_ = [gndLit]
                elif gndLitTruth == self.mrf.evidence[minTruthLit_[0].gndAtom.idx]:
                    minTruthLit_.append(gndLit)
                # we can stop when we encounter at least two entirely false conjuncts
                if gndLitTruth == 0 and len(minTruthLit_) == 2: 
                    continue
                if len(conjuncts) + len(eqConstraints) >= 2:
                    newConj = self.mrf.mln.logic.conjunction(eqConstraints + conjuncts[1:]).ground(self.mrf, varAssign, allowPartialGroundings=True)
                else:
                    newConj = (eqConstraints + conjuncts[1:])[0]
                self.generateTrueConjunctionGroundings(fIdx, newConj, conjunctsSoFar + [gndLit], minTruthLit_, sndMinTruth_)
        else:
            self.generateTrueConjunctionGroundings(fIdx, None, conjunctsSoFar, minTruthLit, sndMinTruth)
            
    def _computeStatistics(self): 
        self.createVariablesAndEvidence()
        mrf = self.mrf
        log = logging.getLogger('bpll')
        for fIdx, formula in enumerate(mrf.formulas):
            sys.stdout.write('%d/%d\r' % (fIdx, len(mrf.formulas)))
            if False:#self.mrf.mln.logic.isConjunctionOfLiterals(formula):
                log.debug(formula)
#                 print 'grounding:'
#                 print strFormula(formula)
                self.generateTrueConjunctionGroundings(fIdx, formula, [])
            else:
                # go through all ground formulas
                for gndFormula, _ in formula.iterGroundings(mrf, False):
                    # get the set of block indices that the variables appearing in the formula correspond to
                    idxBlocks = set()
                    for idxGA in gndFormula.idxGroundAtoms():
#                        if debug: print self.mrf.gndAtomsByIdx[idxGA]
                        idxBlocks.add(self.mrf.atom2BlockIdx[idxGA])
                    for idxVar in idxBlocks:
                        (idxGA, block) = self.mrf.pllBlocks[idxVar]
                        if idxGA is not None: # ground atom is the variable as it's not in a block
                            # check if formula is true if gnd atom maintains its truth value
                            truth = self.mrf._isTrueGndFormulaGivenEvidence(gndFormula) 
                            if truth:
                                self._addMBCount(idxVar, 2, 0, fIdx, inc=truth)
#                                 self.trueGroundingsCounter[fIdx] = self.trueGroundingsCounter.get(fIdx, 0) + 1
                            # check if formula is true if gnd atom's truth value is inverted
                            old_tv = self.mrf._getEvidence(idxGA)
                            self.mrf._setTemporaryEvidence(idxGA, 1 - old_tv)
                            truth = self.mrf._isTrueGndFormulaGivenEvidence(gndFormula)
                            if truth:
                                self._addMBCount(idxVar, 2, 1, fIdx, inc=truth)
                            self.mrf._removeTemporaryEvidence()
                                 
                        else: # the block is the variable (idxGA is None)
                            size = len(block)
                            idxGATrueone = block[self.evidenceIndices[idxVar]]
                            # check true groundings for each block assigment
                            for idxValue, idxGA in enumerate(block):
                                if idxGA != idxGATrueone:
                                    self.mrf._setTemporaryEvidence(idxGATrueone, 0)
                                    self.mrf._setTemporaryEvidence(idxGA, 1)
                                truth = self.mrf._isTrueGndFormulaGivenEvidence(gndFormula)
                                if truth:
                                    self._addMBCount(idxVar, size, idxValue, fIdx, inc=truth)
                                self.mrf._removeTemporaryEvidence()
#         if self.initWeights:
#             if self.verbose: print 'applying initial weights heuristics...'
#             factor = 0.1
#             for i, f in enumerate(mrf.formulas):
#                 totalGroundings = f.computeNoOfGroundings(mrf)
#                 if totalGroundings - self.trueGroundingsCounter.get(i, 0) == 0:
#                     f.weight = factor * mrf.hard_weight
#                 elif self.trueGroundingsCounter.get(i, 0) == 0:
#                     f.weight = factor * -mrf.hard_weight
#                 else:
#                     f.weight = factor * math.log(self.trueGroundingsCounter.get(i, 0) / float(totalGroundings - self.trueGroundingsCounter.get(i, 0)))
#                 if self.verbose:
#                     print '  log(%d/%d)=%.6f \t%s' % (self.trueGroundingsCounter.get(i, 0), totalGroundings-self.trueGroundingsCounter.get(i, 0), f.weight, strFormula(f))
     
        
#         self.evidence = list(self.mrf.evidence)
#         self.factories = [SmartGroundingFactory(formula, self.mrf) for formula in self.mrf.formulas]
#         self.mrf._clearEvidence()
#         self._computeStatisticsRec(0, True)
#         
#     def _computeStatisticsRec(self, idxVar, allValues):
#         if idxVar == len(self.mrf.pllBlocks):
#             return
#         (idxGA, block) = self.mrf.pllBlocks[idxVar]
#         truthAssignments = []
#     
#         if idxGA is not None:
#             # get the ground atom and its truth value
#             gndAtom = self.mrf.gndAtomsByIdx[idxGA]
#             name = str(gndAtom)
#             isTrue = self.evidence[idxGA]
#             truthAssignments.append({idxGA: isTrue})
#             if allValues: truthAssignments.append({idxGA: not isTrue})
#             valueIndices = [0, 1]
#             blockSize = 2
#         else:
#             idxGATrueone = block[self.evidenceIndices[idxVar]]
#             blockSize = len(block)
#             idxValue = block.index(idxGATrueone)
#             valueIndices = [idxValue]
#             assignment = dict([(idxAtom, False) for idxAtom in block])
#             assignment[idxGATrueone] = True
#             truthAssignments.append(assignment)
#             name = self.mrf._strBlock(block)
#             if allValues:
#                 for idxValue, idxGA in enumerate(block):
#                     if idxGA == idxGATrueone: continue
#                     assignment = dict([(idxAtom, False) for idxAtom in block])
#                     assignment[idxGA] = True
#                     truthAssignments.append(assignment)
#                     valueIndices.append(idxValue)
# 
#         # apply all of the values and update the statistics
#         for i, (valIdx, assignment) in enumerate(zip(valueIndices, truthAssignments)):
# #             print ' ' * idxVar, name, valIdx, assignment
#             
# #             for a, t in assignment.iteritems(): 
# #                 self.mrf.evidence[a] = t            
# #                 for factory in self.factories:
# # #                     print self.mrf.gndAtomsByIdx[a]
# #                     trueGndAtoms = factory.ground(self.mrf.gndAtomsByIdx[a])
# # #                     factory.printTree()
# #                     factory.epochEndsHere()
# #                     print trueGndAtoms
#             
#             self._computeStatisticsRec(idxVar + 1, i == 0 and allValues)

#             for a in assignment:
#                 for f in self.factories: f.undoEpoch() 
#                 self.mrf.evidence[a] = None
                
        
# 
# def getMatchingTuples(assignment, assignments, gndAtomIndices):
#     matchingTuples = []
#     atomIndices = []
#     for i, ass in enumerate(assignments):
#         skip = False
#         for tuple in ass:
#             for tuple2 in assignment:
#                 if tuple[0] == tuple2[0] and tuple[1] != tuple2[1]:
#                     skip = True
#                     break
#             if skip: break
#         if skip: continue
#         matchingTuples.append(ass)
#         atomIndices.append(gndAtomIndices[i])
#     return matchingTuples, atomIndices
# 
#         
# class BPLLGroundingFactory(DefaultGroundingFactory):
#     '''
#     This class implements an "efficient" grounding algorithm for conjunctions
#     when BPLL learning is used. It exploits the fact that we can tell
#     the number of true groundings for a conjunction instantaneously:
#     it is true if and only if all its conjuncts are true.
#     '''
# 
#     def getValidVariableAssignments(self, conjunction, gndAtoms):
#         variableAssignments = []
#         gndAtomIndices = []
#         for lit in conjunction.children:
#             if isinstance(lit, fol.Equality): continue
#             assignments = []
#             atomIndices = []
#             for gndLit, _ in lit.iterGroundings(self.mrf):
#                 assignment = []
#                 if not (gndLit.gndAtom.idx in gndAtoms): break
#                 for (p1, p2) in zip(lit.params, gndLit.gndAtom.params):
#                     if grammar.isVar(p1):
#                         assignment.append((p1, p2))
#                 assignments.append(tuple(assignment))
#                 atomIndices.append(gndLit.gndAtom.idx)
#             variableAssignments.append(assignments)
#             gndAtomIndices.append(atomIndices)
#         return variableAssignments, gndAtomIndices
#     
#     def extractEqualities(self, formula, equals):
#         '''
#         Returns for the given formula the (in)equality constraints by means
#         of (var, val) or (var, var) tuples.
#         - formula:     the formula under consideration
#         - equals:      determines if euqality or inequality constraints should be considered.
#         '''
#         equalities = []
#         for c in formula.children:
#             if isinstance(c, fol.Equality) and c.negated != equals:
#                 equalities.append((c.params[0], c.params[1]))
#         return equalities
#     
#     def checkEquality(self, assignment, equalities, equals):
#         '''
#         Checks if a an assignment matches a set of (in)equality constraints.
#         Returns False if the constraints are certainly not met, True if they
#         are certainly met (i.e. in case constant symbols being part of the constraints,
#         or a list of constraints the given assignment matches.
#         - assignment:        (variable, value) pair specifying a variable assignment
#         - equalities:        a list of (variable, value) or (variable, variable)
#                              pairs specifying (in)equality constraints.
#         - equals:            specifies if equalities is equality or inequality constraints.
#         '''
#         matchingEqualities = [t for t in equalities if isVar(t[0]) and t[0] in assignment or \
#                               isVar(t[1]) and t[1] in assignment]
#         varEqualities = []
#         for eq in matchingEqualities:
#             if isConstant(eq[0]) and equals != (assignment[1] == eq[0]) or \
#                 isConstant(eq[1]) and equals != (assignment[1] == eq[1]):
#                 return False
#             elif isVar(eq[0]) and eq[0] != assignment[0] or isVar(eq[1]) and eq[1] != assignment[0]:
#                 varEqualities.append(eq)#         self.fcounts = {} 
#         self.blockRelevantFormulas = defaultdict(set)
#         if len(varEqualities) > 0:
#             return varEqualities
#         else: return True
#         
#     def _generateAllGroundings(self, assignments, gndAtomIndices, equalities=[], inequalities=[]):
#         '''
#         - assignments: list of lists of tuples of variable/value pairs, e.g. [[(?x,X1),(?x,X2)],[(?y,Y1),(?z,Z)]]
#                        for each atom in the formula representing all possible variable assignments.
#         - gndAtomIndices: list of lists of the corresponding gnd atom indices.
#         - equalities: list of (variable, value) or (variable, variable) pairs
#                       specifying equality constraints.
#         - inequalities: list of (variable, value) or (variable, variable) pairs
#                         specifying inequality constraints.              
#         '''
#         assert len(assignments) > 0
#         groundings = []
#         for assign, atomIdx in zip(assignments[0], gndAtomIndices[0]):
#             self._generateAllGroundingsRec(set(assign), [atomIdx], assignments[1:], gndAtomIndices[1:], groundings)
#         return groundings
#     
#     def _generateAllGroundingsRec(self, assignment, gndAtomIndices, remainingAssignments, remainingAtomIndices, groundings, equalities=[], inequalities=[]):
#         if len(remainingAssignments) == 0:
# #             print assignment
#             groundings.append(gndAtomIndices)  # we found a true complete grounding
#             return
#         tuples, atoms = getMatchingTuples(assignment, remainingAssignments[0], remainingAtomIndices[0])
#         for t, a in zip(tuples, atoms):
#             # check if (in)equality constraints are violated
#             cont = False
#             for equals, eq in zip((True, False), (equalities, inequalities)):
#                 check = self.checkEquality(t, eq, equals)
#                 if check is False:
#                     cont = True
#                     break
#                 if isinstance(check, list):
#                     for constr in check:
#                         matchingAssignments = [ass for ass in assignment if ass[0] == constr[0] or ass[0] == constr[1]]
#                         for m in matchingAssignments:
#                             if equals != (t[1] == m[1]):
#                                 cont = True
#                                 break
#                     if cont: break 
#             if cont: continue
#             self._generateAllGroundingsRec(assignment.union(set(t)), gndAtomIndices + [a], remainingAssignments[1:], remainingAtomIndices[1:], groundings)
#     
#     def _addMBCount(self, idxVar, size, idxValue, idxWeight,inc=1):
#         self.blockRelevantFormulas[idxVar].add(idxWeight)
#         if idxWeight not in self.fcounts:
#             self.fcounts[idxWeight] = {}
#         d = self.fcounts[idxWeight]
#         if idxVar not in d:
#             d[idxVar] = [0] * size
#         d[idxVar][idxValue] += inc
#     
#     def _createGroundFormulas(self):
#         # filter out conjunctions
#         mrf = self.mrf 
#         mln = mrf.mln    
#         mrf._getPllBlocks()
#         mrf._getAtom2BlockIdx()
#         mrf.evidence = map(lambda x: x is True, mrf.evidence)
#         self.fcounts = {} 
#         self.blockRelevantFormulas = defaultdict(set)
#         trueGndAtoms = set([i for i, v in enumerate(self.mrf.evidence) if v == True])
#         falseGndAtoms = set([i for i, v in enumerate(self.mrf.evidence) if v == False])
#         trueGroundingsCounter = {} # dict: formula -> # true groundings
#         
#         # get evidence indices, the index of the true value for block vars,
#         # or 0 for normal gnd atoms.
#         self.evidenceIndices = []
#         for (idxGA, block) in self.mrf.pllBlocks:
#             if idxGA is not None:
#                 self.evidenceIndices.append(0)
#             else:
#                 # find out which ga is true in the block
#                 idxValueTrueone = -1
#                 for idxValue, idxGA in enumerate(block):
#                     if self.mrf._getEvidence(idxGA):
#                         if idxValueTrueone != -1: 
#                             raise Exception("More than one true ground atom in block '%s'!" % self.mrf._strBlock(block))
#                         idxValueTrueone = idxValue
#                 if idxValueTrueone == -1: raise Exception("No true ground atom in block '%s'!" % self.mrf._strBlock(block))
#                 self.evidenceIndices.append(idxValueTrueone)
#         
#         for fIdx, formula in enumerate(mrf.formulas):
# #             stdout.write('%d/%d\r' % (fIdx, len(mrf.formulas)))
#             if isConjunctionOfLiterals(formula):
# #                 print formula
#                 trueAtomAssignments, trueGndAtomIndices = self.getValidVariableAssignments(formula, trueGndAtoms)
#                 equalities = self.extractEqualities(formula, True)
#                 inequalities = self.extractEqualities(formula, False)
#                 # generate all true groundings of the conjunction
#                 trueGndFormulas = self._generateAllGroundings(trueAtomAssignments, trueGndAtomIndices, equalities, inequalities)
#                 trueGroundingsCounter[formula] = trueGroundingsCounter.get(formula, 0) + len(trueGndFormulas)
#                 for gf in trueGndFormulas:
#                     for atomIdx in gf:
#                         idxVar = mrf.atom2BlockIdx[atomIdx]
#                         (idxGA, block) = mrf.pllBlocks[idxVar]
#                         if idxGA is not None:
#                             self._addMBCount(idxVar, 2, 0, fIdx)
#                         else:
#                             size = len(block)
#                             idxValue = block.index(atomIdx)
#                             self._addMBCount(idxVar, size, idxValue, fIdx)
#                         
#                 # count for each false ground atom the number of ground formulas rendered true if its truth value was inverted
#                 falseAtomAssignments, falseGndAtomIndices = self.getValidVariableAssignments(formula, falseGndAtoms)
#                 
#                 for idx, atom in enumerate(falseAtomAssignments):
#                     if isinstance(formula.children[idx], fol.Equality):
#                         continue # for equality constraints
#                     if reduce(lambda x, y: x or y, mln.blocks.get(formula.children[idx].predName, [False])):
#                         continue
#                     groundFormulas = self._generateAllGroundings(trueAtomAssignments[:idx] + [falseAtomAssignments[idx]] + trueAtomAssignments[idx+1:], 
#                                                             trueGndAtomIndices[:idx] + [falseGndAtomIndices[idx]] + trueGndAtomIndices[idx+1:], equalities, inequalities)
#                     for gf in groundFormulas:
#                         idxVar = mrf.atom2BlockIdx[gf[idx]]
#                         self._addMBCount(idxVar, 2, 1, fIdx)
#             else:
#                 # go through all ground formulas
#                 for gndFormula, _ in formula.iterGroundings(mrf, False):
#                     # get the set of block indices that the variables appearing in the formula correspond to
#                     idxBlocks = set()
#                     for idxGA in gndFormula.idxGroundAtoms():
# #                        if debug: print self.mrf.gndAtomsByIdx[idxGA]
#                         idxBlocks.add(self.mrf.atom2BlockIdx[idxGA])
#                     
#                     if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
#                         trueGroundingsCounter[formula] = trueGroundingsCounter.get(formula, 0) + 1
#                         
#                     for idxVar in idxBlocks:
#                         
#                         (idxGA, block) = self.mrf.pllBlocks[idxVar]
#                     
#                         if idxGA is not None: # ground atom is the variable as it's not in a block
#                             
#                             # check if formula is true if gnd atom maintains its truth value
#                             if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
#                                 self._addMBCount(idxVar, 2, 0, fIdx)
#                             
#                             # check if formula is true if gnd atom's truth value is inverted
#                             old_tv = self.mrf._getEvidence(idxGA)
#                             self.mrf._setTemporaryEvidence(idxGA, not old_tv)
#                             if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
#                                 self._addMBCount(idxVar, 2, 1, fIdx)
#                             self.mrf._removeTemporaryEvidence()
#                                 
#                         else: # the block is the variable (idxGA is None)
#         
#                             size = len(block)
#                             idxGATrueone = block[self.evidenceIndices[idxVar]]
#                             
#                             # check true groundings for each block assigment
#                             for idxValue, idxGA in enumerate(block):
#                                 if idxGA != idxGATrueone:
#                                     self.mrf._setTemporaryEvidence(idxGATrueone, False)
#                                     self.mrf._setTemporaryEvidence(idxGA, True)
#                                 if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
#                                     self._addMBCount(idxVar, size, idxValue, fIdx)
#                                 self.mrf._removeTemporaryEvidence()
#         # apply the initial weights heuristics
#         if self.initWeights:
#             if self.verbose: print 'applying initial weights heuristics...'
#             factor = 0.1
#             for f in mrf.formulas:
#                 totalGroundings = f.computeNoOfGroundings(mrf) 
#                 if totalGroundings - trueGroundingsCounter[f] == 0:
#                     f.weight = factor * mrf.hard_weight
#                 elif trueGroundingsCounter[f] == 0:
#                     f.weight = factor * -mrf.hard_weight
#                 else:
#                     f.weight = factor * math.log(trueGroundingsCounter[f] / float(totalGroundings - trueGroundingsCounter[f]))
#                 if self.verbose:
#                     print '  log(%d/%d)=%.6f \t%s' % (trueGroundingsCounter[f], totalGroundings-trueGroundingsCounter[f], f.weight, strFormula(f))
#         
#         
#             
#     def createDefaultGroundings(self, formulas, indices):
#         mrf = self.mrf
#         assert len(mrf.gndAtoms) > 0
#         
#         # generate all groundings
#         for idxFormula, formula in zip(indices, formulas):
#             for gndFormula, referencedGndAtoms in formula.iterGroundings(mrf, False):
#                 gndFormula.isHard = formula.isHard
#                 gndFormula.weight = formula.weight
#                 if isinstance(gndFormula, fol.TrueFalse):
#                     continue
#                 mrf._addGroundFormula(gndFormula, idxFormula, referencedGndAtoms)
# 
#         # set weights of hard formulas
# #        hard_weight = 20 + max_weight
# #        if verbose: 
# #            print "setting %d hard weights to %f" % (len(mrf.hard_formulas), hard_weight)
# #        for f in mrf.hard_formulas:
# #            if verbose: 
# #                print "  ", strFormula(f)
# #            f.weight = hard_weight
#         
#         self.mln.gndFormulas = mrf.gndFormulas
#         self.mln.gndAtomOccurrencesInGFs = mrf.gndAtomOccurrencesInGFs

      
      
      
        
