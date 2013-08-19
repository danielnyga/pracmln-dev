# Markov Logic Networks -- Branch-and-Bound Search for MPE inference
#
# (C) 2011-2013 by Daniel Nyga (nyga@cs.tum.edu)
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

from utils.undo import Number
from mln.grounding.bnb import GroundingFactory
from logic import grammar
from mln.database import Database
from logic.fol import GroundAtom, Negation


class BranchAndBound(object):
    '''
    Basic branch-and-bound search for MPE inference.
    '''
    
    def __init__(self, mrf):
        self.mrf = mrf
        self.upperbound = float('inf')
        self.best_solution = {}
        self.vars = []
        self.varIdx2GndAtom = {}
        self.gndAtom2VarIndex = {}
        self.createVariables()
        self.transformFormulas()
        self.evidence = dict([(a.idx, a.isTrue(mrf.evidence)) for a in mrf.gndAtoms.values()])
        
    def transformFormulas(self):
        '''
        Converts the formulas into NNF and converts all negative weights to positive ones.
        '''
        self.formulas = []
        for f in self.mrf.formulas:
            w = f.weight
            hard = f.isHard
            if f.weight < 0:
                f_ = Negation([f])
                w = -w
                f = f_
            print w, f
            f = f.toNNF()
            f.weight = w
            f.isHard = hard
            self.formulas.append(f)
        
    def createVariables(self):
        '''
        Create the variables, one binary for each ground atom.
        Considers also mutually exclusive blocks of ground atoms.
        '''
        handledBlocks = set()
        for gndAtom in self.mrf.gndAtoms.values():
            blockName = self.mrf.gndBlockLookup.get(gndAtom.idx, None)
            if blockName is not None:
                if blockName not in handledBlocks:
                    # create a new variable
                    varIdx = len(self.vars)
                    self.vars.append(blockName)
                    # create the mappings
                    for gndAtomIdx in self.mrf.gndBlocks[blockName]:
                        self.gndAtom2VarIndex[self.mrf.gndAtomsByIdx[gndAtomIdx]] = varIdx
                    self.varIdx2GndAtom[varIdx] = [self.mrf.gndAtomsByIdx[i] for i in self.mrf.gndBlocks[blockName]]
                    handledBlocks.add(blockName)
            else:
                varIdx = len(self.vars)
                self.vars.append(str(gndAtom))
                self.gndAtom2VarIndex[gndAtom] = varIdx
                self.varIdx2GndAtom[varIdx] = [gndAtom]
    
    def _getVariableValue(self, varIdx):
        '''
        Returns True/False for binary variables; the True ground atom for
        mutex constraints, or None if the truth value cannot be determined.
        '''
        gndAtoms = self.varIdx2GndAtom[varIdx]
        if len(gndAtoms) == 1:
            return gndAtoms[0].isTrue(self.evidence)
        else:
            return next((atom for atom in gndAtoms if atom.isTrue(self.evidence)), None)
    
    def _isEvidenceVariable(self, varIdx):
        val = self._getVariableValue(varIdx)
        return type(val) is bool or isinstance(val, GroundAtom)
        
    def search(self):
        self.costs = 0.
        
        # sort the formulas
        self.factories = [GroundingFactory(f, self.mrf) for f in sorted(self.formulas, key=lambda x: x.weight, reverse=True)]
        
        # sort the ground atoms
        atoms = [i for i, _ in enumerate(self.vars) if self._isEvidenceVariable(i)]
        nonEvidenceVars = [i for i, _ in enumerate(self.vars) if not self._isEvidenceVariable(i)]
        atoms.extend([v for v in nonEvidenceVars if len(self.varIdx2GndAtom[v]) > 1])
        atoms.extend([v for v in nonEvidenceVars if len(self.varIdx2GndAtom[v]) == 1])
        self.mrf._clearEvidence()
#         atoms.extend([i for i, _ in enumerate(self.vars) if self.mrf.evidence[self.varIdx2GndAtom[i][0].idx] == True])
        self._recursive_expand(atoms, 0.)
        
    def _recursive_expand(self, variables, lowerbound):
        # if we have found a solution, update the global upper bound
        indent = ''
        for _ in range(len(self.varIdx2GndAtom)-len(variables)): indent += '    '
        if len(variables) == 0: # all gndAtoms have been assigned
            if lowerbound <= self.upperbound:
                solution = dict([(str(a), self.mrf.evidence[a.idx]) for a in self.mrf.gndAtoms.values()])
#                 print indent + 'New solution:', solution
#                 print indent + 'costs:', lowerbound
                self.upperbound = lowerbound
                self.best_solution = solution
            return 
        # generate the truth assignments to be tested
        variable = variables[0]
        gndAtoms = self.varIdx2GndAtom[variable]
        truthAssignments = []
        if len(gndAtoms) == 1: # binary variable
            if self._isEvidenceVariable(variable):
                truthAssignments.append({gndAtoms[0]: self._getVariableValue(variable)})
            else:
                valFromSolution = self.best_solution.get(str(gndAtoms[0]), None)
                truthAssignments.append({gndAtoms[0]: valFromSolution if valFromSolution is not None else False})
                truthAssignments.append({gndAtoms[0]: not valFromSolution if valFromSolution is not None else True})
#                 truthAssignments.append({gndAtoms[0]: False})
#                 truthAssignments.append({gndAtoms[0]: True})
        elif len(gndAtoms) > 1: # mutex constraint
            for trueGndAtom in gndAtoms:
                if trueGndAtom.isTrue(self.mrf.evidence) == False:
                    continue
                assignment = dict([(gndAtom, False) for gndAtom in gndAtoms])
                assignment[trueGndAtom] = True
                truthAssignments.append(assignment)
        # test the assignments
#         print truthAssignments
        for truthAssignment in truthAssignments:
            print indent + 'testing', truthAssignment, '(lb=%f)' % lowerbound
            # set the temporary evidence
#             self.setEvidence(truthAssignment)
            backtrack = {}
            doBacktracking = False
            costs = .0
            evidence = []
            for gndAtom, truth in truthAssignment.iteritems():
                self.setEvidence({gndAtom: truth})
                evidence.append(gndAtom)
                for factory in self.factories:
                    costs += factory.ground(gndAtom)
                    factory.epochEndsHere()
                    backtrack[factory] = backtrack.get(factory, 0) + 1
#                     print indent + 'LB:' + str(lowerbound + costs)
                    if lowerbound + costs >= self.upperbound:
                        print indent + 'backtracking (C=%.2f >= %.2f=UB)' % (lowerbound + costs, self.upperbound)
                        doBacktracking = True
                        break
                if doBacktracking:
                    break
            if not doBacktracking:
                self._recursive_expand(variables[1:], lowerbound + costs)
            # revoke the groundings of the already grounded factories
            for f in backtrack:
                for _ in range(backtrack[f]): f.undoEpoch()
            # remove the evidence
            for e in evidence:
                self.neutralizeEvidence({e: None})
    
    def setEvidence(self, assignment):
        for gndAtom in assignment:
            self.mrf._setEvidence(gndAtom.idx, assignment[gndAtom])
            
    def neutralizeEvidence(self, assignment):
        for gndAtom in assignment:
            self.mrf._setEvidence(gndAtom.idx, None)
            
if __name__ == '__main__':
    from mln.MarkovLogicNetwork import MLN
    
    mln = MLN()
    mln.declarePredicate('foo', ['x', 'y'], functional=[1])
    mln.declarePredicate('bar', ['y','z'])
     
    f = grammar.parseFormula('foo(?x1,?y1) ^ foo(?x2,?y1) ^ bar(?y3,Y) ^ bar(?y3, ?z2)')
    mln.addFormula(f, 1)
    f = grammar.parseFormula('!foo(?x1,?y1) v !foo(?x2,?y1) v !bar(?y3,Y) v !bar(?y3, ?z2)')
    mln.addFormula(f, 1.1)
#    mln.addDomainValue('x', 'Z')
     
    db = Database(mln)
    db.addGroundAtom('!foo(X, Fred)')
    db.addGroundAtom('!foo(X, Ann)')
    db.addGroundAtom('!bar(Fred, Z)')
    db.addGroundAtom('bar(Bob, Y)')
     
     
    mrf = mln.groundMRF(db, simplify=False)
     
    bnb = BranchAndBound(mrf)
    bnb.search()
    print 'optimal solution (cost %f):' % bnb.upperbound
    for s in sorted(bnb.best_solution):
        print '', s, ':', bnb.best_solution[s]
         
    exit(0)
#     groundingFactories = [GroundingFactory(f, mrf) for f in mrf.formulas]
#      
#     atoms = list(mrf.gndAtoms.keys())
#     shuffle(atoms)
#     for f in mrf.formulas: print f
#     print mrf.domains
#     for atom in atoms:
#         print 'grounding with', atom
#         for factory in groundingFactories:
#             factory.ground(mrf.gndAtoms[atom])