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

from DefaultGrounding import DefaultGroundingFactory
from logic import fol, grammar
from sys import stdout
import time
from collections import defaultdict
import math
from logic.fol import isConjunctionOfLiterals, isVar
from mln.util import strFormula
from logic.grammar import isConstant
# from logic.fol import isConjunctionOfLiterals


def getMatchingTuples(assignment, assignments, gndAtomIndices):
    matchingTuples = []
    atomIndices = []
    for i, ass in enumerate(assignments):
        try:
            for tuple in ass:
                for tuple2 in assignment:
                    if tuple[0] == tuple2[0] and tuple[1] != tuple2[1]:
                        raise
            matchingTuples.append(ass)
            atomIndices.append(gndAtomIndices[i])
        except: pass
    return matchingTuples, atomIndices

        
class BPLLGroundingFactory(DefaultGroundingFactory):
    '''
    This class implements an "efficient" grounding algorithm for conjunctions
    when BPLL learning is used. It exploits the fact that we can tell
    the number of true groundings for a conjunction instantaneously:
    it is true if and only if all its conjuncts are true.
    '''

    def getValidVariableAssignments(self, conjunction, trueOrFalse, gndAtoms):
        variableAssignments = []
        gndAtomIndices = []
        for lit in conjunction.children:
            if isinstance(lit, fol.Equality): continue
            assignments = []
            atomIndices = []
            for gndAtom in gndAtoms:
                try:
                    if gndAtom.predName != lit.predName: 
                        continue
                    assignment = []
                    for (p1, p2) in zip(lit.params, gndAtom.params):
                        if grammar.isVar(p1):
                            assignment.append((p1, p2))
                        elif p1 != p2: raise
                    assignments.append(tuple(assignment))
                    atomIndices.append(gndAtom.idx)
                except: pass
            variableAssignments.append(assignments)
            gndAtomIndices.append(atomIndices)
        return variableAssignments, gndAtomIndices
    
    def extractEqualities(self, formula, equals):
        '''
        Returns for the given formula the (in)equality constraints by means
        of (var, val) or (var, var) tuples.
        - formula:     the formula under consideration
        - equals:      determines if euqality or inequality constraints should be considered.
        '''
        equalities = []
        for c in formula.children:
            if isinstance(c, fol.Equality) and c.negated != equals:
                equalities.append((c.params[0], c.params[1]))
        return equalities
    
    def checkEquality(self, assignment, equalities, equals):
        '''
        Checks if a an assignment matches a set of (in)equality constraints.
        Returns False if the constraints are certainly not met, True if they
        are certainly met (i.e. in case constant symbols being part of the constraints,
        or a list of constraints the given assignment matches.
        - assignment:        (variable, value) pair specifying a variable assignment
        - equalities:        a list of (variable, value) or (variable, variable)
                             pairs specifying (in)equality constraints.
        - equals:            specifies if equalities is equality or inequality constraints.
        '''
        matchingEqualities = [t for t in equalities if isVar(t[0]) and t[0] in assignment or \
                              isVar(t[1]) and t[1] in assignment]
        varEqualities = []
        for eq in matchingEqualities:
            if isConstant(eq[0]) and equals != (assignment[1] == eq[0]) or \
                isConstant(eq[1]) and equals != (assignment[1] == eq[1]):
                return False
            elif isVar(eq[0]) and eq[0] != assignment[0] or isVar(eq[1]) and eq[1] != assignment[0]:
                varEqualities.append(eq)
        if len(varEqualities) > 0:
            return varEqualities
        else: return True
        
    def _generateAllGroundings(self, assignments, gndAtomIndices, equalities=[], inequalities=[]):
        '''
        - assignments: list of lists of tuples of variable/value pairs, e.g. [[(?x,X1),(?x,X2)],[(?y,Y1),(?z,Z)]]
                       for each atom in the formula representing all possible variable assignments.
        - gndAtomIndices: list of lists of the corresponding gnd atom indices.
        - equalities: list of (variable, value) or (variable, variable) pairs
                      specifying equality constraints.
        - inequalities: list of (variable, value) or (variable, variable) pairs
                        specifying inequality constraints.              
        '''
        assert len(assignments) > 0
        groundings = []
        for assign, atomIdx in zip(assignments[0], gndAtomIndices[0]):
            self._generateAllGroundingsRec(set(assign), [atomIdx], assignments[1:], gndAtomIndices[1:], groundings)
        return groundings
    
    def _generateAllGroundingsRec(self, assignment, gndAtomIndices, remainingAssignments, remainingAtomIndices, groundings, equalities=[], inequalities=[]):
        if len(remainingAssignments) == 0:
#             print assignment
            groundings.append(gndAtomIndices)  # we found a true complete grounding
            return
        tuples, atoms = getMatchingTuples(assignment, remainingAssignments[0], remainingAtomIndices[0])
        for t, a in zip(tuples, atoms):
            # check if (in)equality constraints are violated
            cont = False
            for equals, eq in zip((True, False), (equalities, inequalities)):
                check = self.checkEquality(t, eq, equals)
                if check is False:
                    cont = True
                    break
                if isinstance(check, list):
                    for constr in check:
                        matchingAssignments = [ass for ass in assignment if ass[0] == constr[0] or ass[0] == constr[1]]
                        for m in matchingAssignments:
                            if equals != (t[1] == m[1]):
                                cont = True
                                break
                    if cont: break 
            if cont: continue
            self._generateAllGroundingsRec(assignment.union(set(t)), gndAtomIndices + [a], remainingAssignments[1:], remainingAtomIndices[1:], groundings)
    
    def _addMBCount(self, idxVar, size, idxValue, idxWeight):
        self.blockRelevantFormulas[idxVar].add(idxWeight)
        if idxWeight not in self.fcounts:
            self.fcounts[idxWeight] = {}
        d = self.fcounts[idxWeight]
        if idxVar not in d:
            d[idxVar] = [0] * size
        d[idxVar][idxValue] += 1
    
    def _createGroundFormulas(self):
        # filter out conjunctions
        mrf = self.mrf 
        mln = mrf.mln    
        mrf._getPllBlocks()
        mrf._getAtom2BlockIdx()
        mrf.evidence = map(lambda x: x is True, mrf.evidence)
        self.fcounts = {} 
        self.blockRelevantFormulas = defaultdict(set)
        trueGndAtoms = [self.mrf.gndAtomsByIdx[i] for i, v in enumerate(self.mrf.evidence) if v == True]
        falseGndAtoms = [self.mrf.gndAtomsByIdx[i] for i, v in enumerate(self.mrf.evidence) if v == False]
        trueGroundingsCounter = {} # dict: formula -> # true groundings
        
        # get evidence indices
        self.evidenceIndices = []
        for (idxGA, block) in self.mrf.pllBlocks:
            if idxGA is not None:
                self.evidenceIndices.append(0)
            else:
                # find out which ga is true in the block
                idxValueTrueone = -1
                for idxValue, idxGA in enumerate(block):
                    if self.mrf._getEvidence(idxGA):
                        if idxValueTrueone != -1: raise Exception("More than one true ground atom in block '%s'!" % self.mrf._strBlock(block))
                        idxValueTrueone = idxValue
                if idxValueTrueone == -1: raise Exception("No true ground atom in block '%s'!" % self.mrf._strBlock(block))
                self.evidenceIndices.append(idxValueTrueone)
        
        for fIdx, formula in enumerate(mrf.formulas):
#             stdout.write('%d/%d\r' % (fIdx, len(mrf.formulas)))
            if isConjunctionOfLiterals(formula):
#                 print formula
                trueAtomAssignments, trueGndAtomIndices = self.getValidVariableAssignments(formula, True, trueGndAtoms)
                equalities = self.extractEqualities(formula, True)
                inequalities = self.extractEqualities(formula, False)
                # generate all true groundings of the conjunction
                trueGndFormulas = self._generateAllGroundings(trueAtomAssignments, trueGndAtomIndices, equalities, inequalities)
                trueGroundingsCounter[formula] = trueGroundingsCounter.get(formula, 0) + len(trueGndFormulas)
                for gf in trueGndFormulas:
                    for atomIdx in gf:
                        idxVar = mrf.atom2BlockIdx[atomIdx]
                        (idxGA, block) = mrf.pllBlocks[idxVar]
                        if idxGA is not None:
                            self._addMBCount(idxVar, 2, 0, fIdx)
                        else:
                            size = len(block)
                            idxValue = block.index(atomIdx)
                            self._addMBCount(idxVar, size, idxValue, fIdx)
                        
                # count for each false ground atom the number of ground formulas rendered true if its truth value was inverted
                falseAtomAssignments, falseGndAtomIndices = self.getValidVariableAssignments(formula, False, falseGndAtoms)
                
                for idx, atom in enumerate(falseAtomAssignments):
                    if isinstance(formula.children[idx], fol.Equality):
                        continue # for equality constraints
                    if reduce(lambda x, y: x or y, mln.blocks.get(formula.children[idx].predName, [False])):
                        continue
                    groundFormulas = self._generateAllGroundings(trueAtomAssignments[:idx] + [falseAtomAssignments[idx]] + trueAtomAssignments[idx+1:], 
                                                            trueGndAtomIndices[:idx] + [falseGndAtomIndices[idx]] + trueGndAtomIndices[idx+1:], equalities, inequalities)
                    for gf in groundFormulas:
                        idxVar = mrf.atom2BlockIdx[gf[idx]]
                        self._addMBCount(idxVar, 2, 1, fIdx)
            else:
                # go through all ground formulas
                for gndFormula, _ in formula.iterGroundings(mrf, False):
                    # get the set of block indices that the variables appearing in the formula correspond to
                    idxBlocks = set()
                    for idxGA in gndFormula.idxGroundAtoms():
#                        if debug: print self.mrf.gndAtomsByIdx[idxGA]
                        idxBlocks.add(self.mrf.atom2BlockIdx[idxGA])
                    
                    if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
                        trueGroundingsCounter[formula] = trueGroundingsCounter.get(formula, 0) + 1
                        
                    for idxVar in idxBlocks:
                        
                        (idxGA, block) = self.mrf.pllBlocks[idxVar]
                    
                        if idxGA is not None: # ground atom is the variable as it's not in a block
                            
                            # check if formula is true if gnd atom maintains its truth value
                            if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
                                self._addMBCount(idxVar, 2, 0, fIdx)
                            
                            # check if formula is true if gnd atom's truth value is inverted
                            old_tv = self.mrf._getEvidence(idxGA)
                            self.mrf._setTemporaryEvidence(idxGA, not old_tv)
                            if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
                                self._addMBCount(idxVar, 2, 1, fIdx)
                            self.mrf._removeTemporaryEvidence()
                                
                        else: # the block is the variable (idxGA is None)
        
                            size = len(block)
                            idxGATrueone = block[self.evidenceIndices[idxVar]]
                            
                            # check true groundings for each block assigment
                            for idxValue, idxGA in enumerate(block):
                                if idxGA != idxGATrueone:
                                    self.mrf._setTemporaryEvidence(idxGATrueone, False)
                                    self.mrf._setTemporaryEvidence(idxGA, True)
                                if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula):
                                    self._addMBCount(idxVar, size, idxValue, fIdx)
                                self.mrf._removeTemporaryEvidence()
        # apply the initial weights heuristics
        if self.initWeights:
            if self.verbose: print 'applying initial weights heuristics...'
            factor = 0.1
            for f in mrf.formulas:
                totalGroundings = f.computeNoOfGroundings(mrf) 
                if totalGroundings - trueGroundingsCounter[f] == 0:
                    f.weight = factor * mrf.hard_weight
                elif trueGroundingsCounter[f] == 0:
                    f.weight = factor * -mrf.hard_weight
                else:
                    f.weight = factor * math.log(trueGroundingsCounter[f] / float(totalGroundings - trueGroundingsCounter[f]))
                if self.verbose:
                    print '  log(%d/%d)=%.6f \t%s' % (trueGroundingsCounter[f], totalGroundings-trueGroundingsCounter[f], f.weight, strFormula(f))
        
        
            
    def createDefaultGroundings(self, formulas, indices):
        mrf = self.mrf
        assert len(mrf.gndAtoms) > 0
        
        # generate all groundings
        for idxFormula, formula in zip(indices, formulas):
            for gndFormula, referencedGndAtoms in formula.iterGroundings(mrf, False):
                gndFormula.isHard = formula.isHard
                gndFormula.weight = formula.weight
                if isinstance(gndFormula, fol.TrueFalse):
                    continue
                mrf._addGroundFormula(gndFormula, idxFormula, referencedGndAtoms)

        # set weights of hard formulas
#        hard_weight = 20 + max_weight
#        if verbose: 
#            print "setting %d hard weights to %f" % (len(mrf.hard_formulas), hard_weight)
#        for f in mrf.hard_formulas:
#            if verbose: 
#                print "  ", strFormula(f)
#            f.weight = hard_weight
        
        self.mln.gndFormulas = mrf.gndFormulas
        self.mln.gndAtomOccurrencesInGFs = mrf.gndAtomOccurrencesInGFs

      
      
      
        
