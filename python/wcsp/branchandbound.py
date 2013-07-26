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


class BranchAndBound(object):
    
    def __init__(self, mrf):
        self.mrf = mrf
        self.upperbound = float('inf')
        self.best_solution = None
        self.vars = []
        self.varIdx2GndAtom = {}
        self.gndAtom2VarIndex = {}
        self.createVariables()
        
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
#         self._simplifyVariables()
    
    def _getVariableValue(self, varIdx):
        return self.mrf.evidence[self.varIdx2GndAtom[varIdx][0].idx]
    
    def _isEvidenceVariable(self, varIdx):
        return self._getVariableValue(varIdx) != None
    
    def _simplifyVariables(self):
        '''
        Removes variables that are already given by the evidence.
        '''
        sf_varIdx2GndAtoms = {}
        sf_gndAtom2VarIdx = {}
        sf_vars = []
        evidence = [i for i, e in enumerate(self.mrf.evidence) if e is not None]
        for varIdx, var in enumerate(self.vars):
            gndAtoms = self.varIdx2GndAtom[varIdx]
            unknownVars = filter(lambda x: x.idx not in evidence, gndAtoms)
            if len(unknownVars) > 0:
                # all gndAtoms are set by the evidence: remove the variable
                sfVarIdx = len(sf_vars)
                sf_vars.append(var)
                for gndAtom in self.varIdx2GndAtom[varIdx]:
                    sf_gndAtom2VarIdx[gndAtom] = sfVarIdx
                sf_varIdx2GndAtoms[sfVarIdx] = self.varIdx2GndAtom[varIdx]
        self.vars = sf_vars
        self.gndAtom2VarIndex = sf_gndAtom2VarIdx
        self.varIdx2GndAtom = sf_varIdx2GndAtoms
        
    def search(self):
        self.costs = Number(0.)
        self.factories = [GroundingFactory(f, self.mrf) for f in self.mrf.formulas]
        atoms = [i for i, _ in enumerate(self.vars) if self.mrf.evidence[self.varIdx2GndAtom[i][0].idx] == False]
        atoms.extend([i for i, _ in enumerate(self.vars) if self.mrf.evidence[self.varIdx2GndAtom[i][0].idx] == None])
        atoms.extend([i for i, _ in enumerate(self.vars) if self.mrf.evidence[self.varIdx2GndAtom[i][0].idx] == True])
        self._recursive_expand(atoms, 0.)
        
    def _recursive_expand(self, variables, lowerbound):
        # if we have found a solution, update the global upper bound
        indent = ''
        for _ in range(len(self.varIdx2GndAtom)-len(variables)): indent += '    '
        if len(variables) == 0: # all gndAtoms have been assigned
            if lowerbound <= self.upperbound:
                solution = dict([(str(a), self.mrf.evidence[a.idx]) for a in self.mrf.gndAtoms.values()])
                print indent + 'New solution:', solution
                print indent + 'costs:', lowerbound
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
                truthAssignments.append({gndAtoms[0]: False})
                truthAssignments.append({gndAtoms[0]: True})
#         elif len(gndAtoms) > 1: # mutex constraint
# #             if self._isEvidenceVariable(variable):
# #                 assignment = dict([(gndAtom, self._getVariableValue(variable)) for gndAtom in gndAtoms])
#             for trueGndAtom in gndAtoms:
#                 assignment = dict([(gndAtom, False) for gndAtom in gndAtoms])
#                 truthAssignments.append(assignment)
#                 assignment[trueGndAtom] = True
        # test the assignments
        print truthAssignments
        for truthAssignment in truthAssignments:
            print indent + 'testing', truthAssignment
            # set the temporary evidence
            self.setEvidence(truthAssignment)
            backtrack = []
            doBacktracking = False
            for gndAtom in truthAssignment:
                costs = .0
                for factory in self.factories:
                    costs += factory.ground(gndAtom)
                    factory.epochEndsHere()
                    backtrack.append(factory) 
                    print indent + 'LB:' + str(lowerbound + costs)
                    if lowerbound + costs >= self.upperbound:
                        print indent + 'backtracking (C=%.2f >= %.2f=UB)' % (lowerbound + costs, self.upperbound)
                        doBacktracking = True
                        break
                if doBacktracking: break
                else:
                    self._recursive_expand(variables[1:], lowerbound + costs)
            # revoke the groundings of the already grounded factories
            for f in backtrack:
                f.undoEpoch()
            # remove the evidence
            self.neutralizeEvidence(truthAssignment)
    
    def setEvidence(self, assignment):
        for gndAtom in assignment:
            self.mrf._setEvidence(gndAtom.idx, assignment[gndAtom])
            
    def neutralizeEvidence(self, assignment):
        for gndAtom in assignment:
            self.mrf._setEvidence(gndAtom.idx, None)
            
if __name__ == '__main__':
    
#     mln = PRACMLN()
#     mln.declarePredicate('foo', ['x', 'y'])#, functional=[1])
#     mln.declarePredicate('bar', ['y','z'])
#     
#     f = grammar.parseFormula('foo(?x1,?y1) ^ foo(?x2,?y1) ^ bar(?y3,Y) ^ bar(?y3, ?z2)')
#     mln.addFormula(f, 1)
#     f = grammar.parseFormula('!foo(?x1,?y1) v !foo(?x2,?y1) v !bar(?y3,Z) v !bar(?y3, ?z2)')
# #     mln.addFormula(f, 1.1)
# #    mln.addDomainValue('x', 'Z')
#     
#     db = PRACDatabase(mln)
#     db.addGroundAtom('!foo(X, Fred)')
#     db.addGroundAtom('!foo(X, Ann)')
#     db.addGroundAtom('!bar(Fred, Z)')
#     db.addGroundAtom('bar(Bob, Y)')
#     
#     
#     mrf = mln.groundMRF(db, simplify=False)
#     
#     bnb = BranchAndBound(mrf)
#     bnb.search()
#     for s in bnb.best_solution:
#         print s, ':', bnb.best_solution[s]
#         
#     exit(0)
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