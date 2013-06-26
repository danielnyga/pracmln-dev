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
from logic import FOL, grammar
from sys import stdout
import time
from collections import defaultdict

def isConjunctionOfLiterals(f):
    if not type(f) is FOL.Conjunction:
        return False
    for child in f.children:
        if not isinstance(child, FOL.Lit):
            return False
    return True

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
        
    def _generateAllGroundings(self, assignments, gndAtomIndices):
        assert len(assignments) > 0
        groundings = []
        for assign, atomIdx in zip(assignments[0], gndAtomIndices[0]):
            self._generateAllGroundingsRec(set(assign), [atomIdx], assignments[1:], gndAtomIndices[1:], groundings)
        return groundings
    
    def _generateAllGroundingsRec(self, assignment, gndAtomIndices, remainingAssignments, remainingAtomIndices, groundings):
        if len(remainingAssignments) == 0:
            groundings.append(gndAtomIndices)  # we found a true complete grounding
            return
        tuples, atoms = getMatchingTuples(assignment, remainingAssignments[0], remainingAtomIndices[0])
        for t, a in zip(tuples, atoms):
            self._generateAllGroundingsRec(assignment.union(set(t)), gndAtomIndices + [a], remainingAssignments[1:], remainingAtomIndices[1:], groundings)
    
    def _addMBCount(self, idxVar, size, idxValue, idxWeight):
        self.blockRelevantFormulas[idxVar].add(idxWeight)
        if idxWeight not in self.fcounts:
            self.fcounts[idxWeight] = {}
        d = self.fcounts[idxWeight]
        if idxVar not in d:
            d[idxVar] = [0] * size
        d[idxVar][idxValue] += 1
    
    def _createGroundFormulas(self, verbose):
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
            stdout.write('%d/%d\r' % (fIdx, len(mrf.formulas)))
            
            if isConjunctionOfLiterals(formula):
                trueAtomAssignments, trueGndAtomIndices = self.getValidVariableAssignments(formula, True, trueGndAtoms)
            
                # generate all true groundings of the conjunction
                trueGndFormulas = self._generateAllGroundings(trueAtomAssignments, trueGndAtomIndices)
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
                    if reduce(lambda x, y: x or y, mln.blocks.get(formula.children[idx].predName, [False])):
                        continue
                    groundFormulas = self._generateAllGroundings(trueAtomAssignments[:idx] + [falseAtomAssignments[idx]] + trueAtomAssignments[idx+1:], 
                                                            trueGndAtomIndices[:idx] + [falseGndAtomIndices[idx]] + trueGndAtomIndices[idx+1:])
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
        
        
#        conjunctions = []
#        otherFormulas = []
#        conjIndices = []
#        otherIndices = []
#        for i, f in enumerate(self.mrf.formulas):
#            if isConjunctionOfLiterals(f):
#                conjunctions.append(f)
#                conjIndices.append(i)
#            else:
#                otherFormulas.append(f)
#                otherIndices.append(i)
	
        
#        for conjIdx, conj in enumerate(conjunctions):
#            stdout.write('%d/%d\r' % (conjIdx, len(conjunctions)))
#            
#            trueAtomAssignments, trueGndAtomIndices = self.getValidVariableAssignments(conj, True, trueGndAtoms)
#            
#            # generate all true groundings of the conjunction
#            trueGndFormulas = self._generateAllGroundings(trueAtomAssignments, trueGndAtomIndices)
#            for gf in trueGndFormulas:
#                for atomIdx in gf:
#                    idxVar = mrf.atom2BlockIdx[atomIdx]
#                    (idxGA, block) = mrf.pllBlocks[idxVar]
#                    if idxGA is not None:
#                        self._addMBCount(idxVar, 2, 0, conjIndices[conjIdx])
#                    else:
#                        size = len(block)
#                        idxValue = block.index(atomIdx)
#                        self._addMBCount(idxVar, size, idxValue, conjIndices[conjIdx])
#                    
#            # count for each false ground atom the number of ground formulas rendered true if its truth value was inverted
#            falseAtomAssignments, falseGndAtomIndices = self.getValidVariableAssignments(conj, False, falseGndAtoms)
#            
#            for idx, atom in enumerate(falseAtomAssignments):
#                if reduce(lambda x, y: x or y, mln.blocks.get(conj.children[idx].predName, [False])):
#                    continue
#                groundFormulas = self._generateAllGroundings(trueAtomAssignments[:idx] + [falseAtomAssignments[idx]] + trueAtomAssignments[idx+1:], 
#                                                        trueGndAtomIndices[:idx] + [falseGndAtomIndices[idx]] + trueGndAtomIndices[idx+1:])
#                for gf in groundFormulas:
#                    idxVar = mrf.atom2BlockIdx[gf[idx]]
#                    self._addMBCount(idxVar, 2, 1, conjIndices[conjIdx])
                        
#            self.createDefaultGroundings(otherFormulas, otherIndices)
            
    def createDefaultGroundings(self, formulas, indices):
        mrf = self.mrf
        assert len(mrf.gndAtoms) > 0
        
        # generate all groundings
        for idxFormula, formula in zip(indices, formulas):
            for gndFormula, referencedGndAtoms in formula.iterGroundings(mrf, False):
                gndFormula.isHard = formula.isHard
                gndFormula.weight = formula.weight
                if isinstance(gndFormula, FOL.TrueFalse):
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

      
      
      
        
