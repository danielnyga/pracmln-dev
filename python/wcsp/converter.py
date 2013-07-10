# Markov Logic Networks -- WCSP conversion
#
# (C) 2012 by Daniel Nyga (nyga@cs.tum.edu)
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

from MLN.MarkovLogicNetwork import MLN, Database
import bisect
from wcsp import WCSP
import sys
from wcsp import Constraint
from logic.FOL import Negation, GroundAtom, GroundLit
import utils
from logic.FOL import isConjunctionOfLiterals
from logic.FOL import isDisjunctionOfLiterals

class WCSPConverter(object):
    '''
    Class for converting an MLN into a WCSP problem for efficient
    MPE inference.
    '''
    
    def __init__(self, mrf):
        self.mrf = mrf
        self.mln = mrf.mln
        self.vars = []
        self.varIdx2GndAtom = {}
        self.gndAtom2VarIndex = {}
        self.createVariables()
        self.simplifyVariables()
        self.divisor = self.computeDivisor()
        self.top = self.computeHardCosts()
        self.constraintBySignature = {}
    
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

        
    def simplifyVariables(self):
        '''
        Removes variables that are already given by the evidence.
        '''
        sf_varIdx2GndAtoms = {}
        sf_gndAtom2VarIdx = {}
        sf_vars = []
        evidence = [i for i, e in enumerate(self.mrf.evidence) if e is not None]
        for varIdx, var in enumerate(self.vars):
            gndAtoms = self.varIdx2GndAtom[varIdx]
#            print map(str,gndAtoms)
            if len(filter(lambda x: x.idx not in evidence, gndAtoms)) > 0:
                # all gndAtoms are set by the evidence: remove the variable
#                print 'simplified', map(str,gndAtoms)
                sfVarIdx = len(sf_vars)
                sf_vars.append(var)
                for gndAtom in self.varIdx2GndAtom[varIdx]:
                    sf_gndAtom2VarIdx[gndAtom] = sfVarIdx
                sf_varIdx2GndAtoms[sfVarIdx] = self.varIdx2GndAtom[varIdx]
        self.vars = sf_vars
        self.gndAtom2VarIndex = sf_gndAtom2VarIdx
        self.varIdx2GndAtom = sf_varIdx2GndAtoms
        
    def computeDivisor(self):
        '''
        Computes a divisor for making all formula weights integers.
        '''
        # store all weights in a sorted list
        weights = []
        minWeight = None
        for f in self.mln.formulas:
            if f.isHard or f.weight == 0.0: continue
            w = abs(f.weight)
            if w in weights:
                continue
            bisect.insort(weights, w)
            if minWeight is None or w < minWeight and w > 0:
                minWeight = w
        
        # compute the smallest difference between subsequent weights
        deltaMin = None
        w1 = weights[0]
        for w2 in weights[1:]:
            diff = w2 - w1
            if deltaMin is None or diff < deltaMin:
                deltaMin = diff
            w1 = w2

        divisor = 1.0
        if minWeight < 1.0:
            divisor *= minWeight
        if deltaMin < 1.0:
            divisor *= deltaMin
        return divisor
    
    def computeHardCosts(self):
        '''
        Computes the costs for hard constraints that determine
        costs for entirely inconsistent worlds (0 probability).
        '''
        costSum = long(0)
        for f in self.mln.gndFormulas:
            if f.isHard or f.weight == 0.0: continue
#            print f.weight, f, self.divisor
            cost = abs(round(float(f.weight) / self.divisor))
            newSum = costSum + cost
            if newSum < costSum:
                raise Exception("Numeric Overflow")
            costSum = newSum
        top = costSum + 1
        if top < costSum:
            raise Exception("Numeric Overflow")
        return long(top)
    
    def generateEvidenceConstraints(self):
        '''
        Creates a hard constraint for every evidence variable that
        could not be eliminated by variable simplification.
        '''
        constraints = []
        for i,e in [(i, e) for i, e in enumerate(self.mrf.evidence) if not e is None]:
            gndAtom = self.mrf.gndAtomsByIdx[i]
            varIdx = self.gndAtom2VarIndex.get(gndAtom, None)
            if varIdx is None: continue
#            print i,e
            block = self.varIdx2GndAtom[varIdx]
            value = block.index(gndAtom)
            cost = 0
            defCost = self.top
            if not e: 
                cost = self.top
                defCost = 0
            constraint = Constraint([varIdx], [[value, cost]], defCost)
            constraints.append(constraint)
        return constraints
    
    def generateConstraint(self, wcsp, wf):
        '''
        Generates and adds a constraint from a given weighted formula.
        '''
        if wf.weight < 0:
            f = Negation([wf])
            f.weight = abs(wf.weight)
            f.isHard = wf.isHard
        else: f = wf
        f_ = f.toNNF()
        f_.weight = f.weight
        f_.isHard = f.isHard 
        idxGndAtoms = f_.idxGroundAtoms()
        gndAtoms = map(lambda x: self.mrf.gndAtomsByIdx[x], idxGndAtoms)
        varIndices = set(map(lambda x: self.gndAtom2VarIndex[x], gndAtoms))
        varIndices = tuple(sorted(varIndices))
        if f_.isHard:
            cost = self.top
        else:
            cost = long(round(f_.weight / self.divisor))
        
        # collect the constraint tuples
        true, false = self.gatherConstraintTuples(wcsp, varIndices, f_)
#        print true, false
        constraint = Constraint(varIndices)
        tuples = None
        if true is None or false is not None and len(true) > len(false):
            constraint.defCost = 0
            tuples = false
        else:
            constraint.defCost = cost
            cost = 0
            tuples = true
        for t in tuples:
            constraint.addTuple(t, cost)
            
        # merge the constraint if possible
        cOld = self.constraintBySignature.get(varIndices, None)
        if not cOld is None:
            for t in constraint.tuples.keys():
                tOldCosts = cOld.tuples.get(t, None)
                if tOldCosts is not None:
                    assert (cost + tOldCosts >= tOldCosts)
                    cOld.addTuple(t, cost + tOldCosts)
                else:
                    assert (cost + cOld.defCost >= cOld.defCost)
                    cOld.addTuple(t, cost + cOld.defCost)
            if constraint.defCost != 0:
                for t in filter(lambda x: x not in constraint.tuples.keys(), cOld.tuples.keys()):
                    oldCost = cOld.tuples[t]
                    cOld.addTuple(t, oldCost + constraint.defCost)
            cOld.defCost += constraint.defCost
        else:
            self.constraintBySignature[varIndices] = constraint
            wcsp.constraints.append(constraint)
        
    def gatherConstraintTuples(self, wcsp, varIndices, formula):
        '''
        Collects and evaluates all tuples that belong to the constraint
        given by a formula. In case of disjunctions and conjunctions,
        this is fairly efficiently since not all combinations
        need to be evaluated.
        ''' 
        try:
            # we can treat conjunctions and disjunctions fairly efficiently
            conj = isConjunctionOfLiterals(formula)
            if not conj and not isDisjunctionOfLiterals(formula): raise
            assignment = [0] * len(varIndices)
            for gndLiteral in formula.children:
                (gndAtom, varVal) = (gndLiteral, True) if isinstance(gndLiteral, GroundAtom) else (gndLiteral.gndAtom, not gndLiteral.negated)
                if not conj: varVal = not varVal
                varVal = 1 if varVal else 0
                varIdx = self.gndAtom2VarIndex[gndAtom]
                if len(self.varIdx2GndAtom[varIdx]) > 1:
                    if isinstance(gndLiteral, GroundLit) and varVal == 0: raise
                    varVal = self.varIdx2GndAtom[varIdx].index(gndAtom)
                assignment[varIndices.index(varIdx)] = varVal
            if conj:
                return [assignment], None
            else:
                return None, [assignment]
        except: 
            # fallback: go through all combinations of truth assignments
            domains = [range(d) for i,d in enumerate(wcsp.domSizes) if i in varIndices]
            trueAssignments = []
            falseAssignments = []
            for c in utils.combinations(domains):
                world = [False] * len(self.mrf.gndAtoms)
                for var, assignment in zip(varIndices, c):
                    if len(self.varIdx2GndAtom[var]) > 1: # mutex constraint
                        world[self.varIdx2GndAtom[var][assignment].idx] = True
                    else:
                        world[self.varIdx2GndAtom[var][0].idx] = assignment > 0
                if formula.isTrue(world):
                    trueAssignments.append(c)
                else:
                    falseAssignments.append(c)
            return trueAssignments, falseAssignments
        
        
    def forbidGndAtom(self, atom, wcsp, trueFalse=True):
        '''
        Adds a unary constraint that prohibits the given ground atom
        being true.
        '''
        varIdx = self.gndAtom2VarIndex[atom]
        varVal = 1
        if len(self.varIdx2GndAtom[varIdx]) > 1:
            varVal = self.varIdx2GndAtom[varIdx].index(atom)
        else:
            varVal = 1 if trueFalse else 0
        c = Constraint([varIdx])
        c.addTuple([varVal], self.top)
        wcsp.addConstraint(c)
        
    def getMostProbableWorldDB(self):
        '''
        Returns a Database object with the most probable truth assignment.
        '''
        wcsp = self.convert()
        solution, _ = wcsp.solve()
        
        resultDB = Database(self.mln)
        resultDB.domains = dict(self.mrf.domains)
        resultDB.evidence = dict(self.mrf.getEvidenceDatabase())
        
        for varIdx, valIdx in enumerate(solution):
            if len(self.varIdx2GndAtom[varIdx]) > 1:
                for v in range(len(self.varIdx2GndAtom[varIdx])):
                    resultDB.evidence[str(self.varIdx2GndAtom[varIdx][v])] = (valIdx == v)
            else:
                resultDB.evidence[str(self.varIdx2GndAtom[varIdx][0])] = (valIdx == 1)
        return resultDB

    def getPseudoDistributionForGndAtom(self, gndAtom):
        '''
        Computes a relative "distribution" for all possible variable assignments of 
        a mutex constraint. This can be used to determine the confidence in particular
        most probable world by comparing the score with the second-most probable one.
        '''
        if isinstance(gndAtom, basestring):
            gndAtom = self.mrf.gndAtoms[gndAtom]
        
        if not isinstance(gndAtom, GroundAtom):
            raise Exception('Argument must be a ground atom')
        
        varIdx = self.gndAtom2VarIndex[gndAtom]
        valIndices = range(len(self.varIdx2GndAtom[varIdx]))
        mutex = len(self.varIdx2GndAtom[varIdx]) > 1
        if not mutex:
            raise Exception("Pseudo distribution is provided for mutex constraints only.")
        wcsp = self.convert()
        atoms = []
        cost = []
        try:
            while len(valIndices) > 0:
                s, c = wcsp.solve()
                if s is None: raise
                val = s[varIdx]
                atom = self.varIdx2GndAtom[varIdx][val]
                self.forbidGndAtom(atom, wcsp)
                valIndices.remove(val)
                cost.append(c)
                atoms.append(atom)
        except: pass                    
        c_max = max(cost)
        for i, c in enumerate(cost):
            cost[i] = c_max - c
        c_sum = sum(cost)
        for i, c in enumerate(cost):
            cost[i] = float(c) / c_sum
        return dict([(a,c) for a, c in zip(atoms, cost)])
        
    def convert(self):
        '''
        Performs a conversion from an MLN into a WCSP.
        '''
        wcsp = WCSP()
        wcsp.top = self.top
        wcsp.domSizes = [max(2,len(self.varIdx2GndAtom[i])) for i, v in enumerate(self.vars)]
        wcsp.constraints.extend(self.generateEvidenceConstraints())
        for f in self.mln.gndFormulas:
            f.weight = self.mln.formulas[f.idxFormula].weight
            f.isHard = self.mln.formulas[f.idxFormula].isHard
            self.generateConstraint(wcsp, f)
        return wcsp

# for debugging only
if __name__ == '__main__':
    
    mln = MLN('/home/nyga/code/prac/models/experimental/deep_sense/priors.mln')
    db = Database(mln, '/home/nyga/code/prac/models/experimental/deep_sense/db/1.db')
    mrf = mln.groundMRF(db)
    
    conv = WCSPConverter(mrf)
    wcsp = conv.convert()
    wcsp.write(sys.stdout)
    solution = wcsp.solve()
    for i, s in enumerate(solution):
        print conv.varIdx2GndAtom[i][0], s, 
        for ga in conv.varIdx2GndAtom[i]: print ga,
        print