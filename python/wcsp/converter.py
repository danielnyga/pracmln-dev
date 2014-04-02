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

import bisect
from wcsp import WCSP
from wcsp import Constraint
import utils
from praclog import logging
from utils import deprecated
from logic.common import Logic
from mln.database import Database
import sys

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
        self.mutexVars = set() # hold indices of mutex variables
        self.createVariables()
        self.simplifyVariables()
#         self.divisor = self.computeDivisor()
#         self.top = self.computeHardCosts()
        self.constraintBySignature = {}
    
    def createVariables(self):
        '''
        Create the variables, one binary for each ground atom.
        Considers also mutually exclusive blocks of ground atoms.
        '''
        handledBlocks = set()
        for gndAtom in self.mrf.gndAtoms.values():
            blockName = self.mrf.gndBlockLookup.get(gndAtom.idx, None)
            varIdx = len(self.vars)
            if blockName is not None:
                if blockName not in handledBlocks:
                    # create a new variable
                    self.vars.append(blockName)
                    # create the mappings
                    for gndAtomIdx in self.mrf.gndBlocks[blockName]:
                        self.gndAtom2VarIndex[self.mrf.gndAtomsByIdx[gndAtomIdx]] = varIdx
                    self.varIdx2GndAtom[varIdx] = [self.mrf.gndAtomsByIdx[i] for i in self.mrf.gndBlocks[blockName]]
                    handledBlocks.add(blockName)
                    self.mutexVars.add(varIdx)
            else:
                self.vars.append(str(gndAtom))
                self.gndAtom2VarIndex[gndAtom] = varIdx
                self.varIdx2GndAtom[varIdx] = [gndAtom]
        
    def simplifyVariables(self):
        '''
        Removes variables that are already given by the evidence.
        '''
        log = logging.getLogger(self.__class__.__name__)
        sf_varIdx2GndAtoms = {}
        sf_gndAtom2VarIdx = {}
        sf_vars = []
        sf_mutexVars = set()
        evidence = [i for i, e in enumerate(self.mrf.evidence) if e is not None]
        for varIdx, var in enumerate(self.vars):
            gndAtoms = filter(lambda x: x.idx not in evidence, self.varIdx2GndAtom[varIdx])
            if len(gndAtoms) > 0: # not all gndAtoms are set by the evidence
                sfVarIdx = len(sf_vars)
                sf_vars.append(var)
                for gndAtom in gndAtoms:
                    sf_gndAtom2VarIdx[gndAtom] = sfVarIdx
                sf_varIdx2GndAtoms[sfVarIdx] = gndAtoms
                if varIdx in self.mutexVars:
                    sf_mutexVars.add(sfVarIdx)
        self.vars = sf_vars
        self.gndAtom2VarIndex = sf_gndAtom2VarIdx
        self.varIdx2GndAtom = sf_varIdx2GndAtoms
        self.mutexVars = sf_mutexVars
            
        
    @deprecated
    def computeDivisor(self):
        '''
        === DEPRECATED: this functionality has been moved to the WCSP class. ===
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
        if len(weights) == 1:
            deltaMin = weights[0]
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
    
    @deprecated
    def computeHardCosts(self):
        '''
        === DEPRECATED: this functionality has been moved to the WCSP class. ===
        Computes the costs for hard constraints that determine
        costs for entirely inconsistent worlds (0 probability).
        '''
        costSum = long(0)
        for f in self.mrf.gndFormulas:
            if f.isHard or f.weight == 0.0: continue
            cost = abs(long(f.weight / self.divisor))
            newSum = costSum + cost
            if newSum < costSum:
                raise Exception("Numeric Overflow")
            costSum = newSum
        top = costSum + 1
        if top < costSum:
            raise Exception("Numeric Overflow")
        if top > WCSPConverter.MAX_COST:
            self.log.error('Maximum costs exceeded: %d > %d' % (top, WCSPConverter.MAX_COST))
            raise
        return long(top)
    
    @deprecated
    def generateEvidenceConstraints(self):
        '''
        === DEPRECATED ===
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
    
    def convert(self):
        '''
        Performs a conversion from an MLN into a WCSP.
        '''
        wcsp = WCSP()
#         wcsp.top = self.top
        wcsp.domSizes = [max(2,len(self.varIdx2GndAtom[i])) for i, _ in enumerate(self.vars)]
#         wcsp.constraints.extend(self.generateEvidenceConstraints())
        log = logging.getLogger('wcsp')
        logic = self.mrf.mln.logic
        if log.level == logging.DEBUG:
            self.mrf.printEvidence()
        # preprocess the ground formulas
        gfs = []
        for gf in self.mrf.gndFormulas:
            gf.weight = self.mln.formulas[gf.idxFormula].weight
            gf.isHard = self.mln.formulas[gf.idxFormula].isHard
            if gf.weight == 0 and not gf.isHard:
                continue
            if gf.weight < 0:
                f = self.mrf.mln.logic.negation([gf])
                f.weight = abs(gf.weight)
                f.isHard = gf.isHard
            else: f = gf
            f_ = f.simplify(self.mrf)
#             print gf.weight
#             if gf.weight == 5000:
#                 log.error('%s ===> %s' % (str(gf), str(f_)))
            if isinstance(f_, Logic.TrueFalse) or gf.weight == 0 and not gf.isHard:
                continue
            f_ = f_.toNNF()
            f_.weight = f.weight
            f_.isHard = f.isHard
            gfs.append(f_)
#         log.info('gfs: ' + str(gfs))
        for f in gfs:
            self.generateConstraint(wcsp, f)
        return wcsp

    def generateConstraint(self, wcsp, wf):
        '''
        Generates and adds a constraint from a given weighted formula.
        '''
        log = logging.getLogger('wcsp')
        idxGndAtoms = wf.idxGroundAtoms()
        gndAtoms = map(lambda x: self.mrf.gndAtomsByIdx[x], idxGndAtoms)
        varIndices = set(map(lambda x: self.gndAtom2VarIndex[x], gndAtoms))
        
        varIndices = tuple(sorted(varIndices))
        # collect the constraint tuples
        cost2assignments = self.gatherConstraintTuples(wcsp, varIndices, wf)
        defaultCost = max(cost2assignments, key=lambda x: float('inf') if cost2assignments[x] == 'else' else len(cost2assignments[x]))
        constraint = Constraint(varIndices, defCost=defaultCost)
        constraint.defCost = defaultCost
        for cost, tuples in cost2assignments.iteritems():
            if cost == defaultCost: continue
            for t in tuples:
                constraint.addTuple(t, cost)
        # merge the constraint if possible
        cOld = self.constraintBySignature.get(varIndices, None)
        if not cOld is None:
            # update all the tuples of the old constraint
            for t, cost in constraint.tuples.iteritems():
                tOldCosts = cOld.tuples.get(t, None)
                if tOldCosts == WCSP.TOP or tOldCosts is None and cOld.defCost == WCSP.TOP: continue
                if tOldCosts is not None:
                    cOld.addTuple(t, WCSP.TOP if cost == WCSP.TOP else cost + tOldCosts)
                else:
                    cOld.addTuple(t, WCSP.TOP if cost == WCSP.TOP else cost + cOld.defCost)
            # update the default costs of the old constraint
            if constraint.defCost != 0 and cOld.defCost != WCSP.TOP:
                for t in filter(lambda x: x not in constraint.tuples, cOld.tuples):
                    oldCost = cOld.tuples[t]
                    if oldCost != WCSP.TOP:
                        cOld.addTuple(t, WCSP.TOP if constraint.defCost == WCSP.TOP else oldCost + constraint.defCost)
                cOld.defCost = WCSP.TOP if constraint.defCost == WCSP.TOP else cOld.defCost + constraint.defCost
            # if the constraint is fully specified by its tuples,
            # simplify it by introducing default costs
            if reduce(lambda x, y: x * y, map(lambda x: wcsp.domSizes[x], varIndices)) == len(cOld.tuples):
                cost2assignments = {}
                for t, c in cOld.tuples.iteritems():
                    ass = cost2assignments.get(c, [])
                    cost2assignments[c] = ass
                    ass.append(t)
                defaultCost = max(cost2assignments, key=lambda x: len(cost2assignments[x]))
                cOld.defCost = defaultCost
                cOld.tuples = {}
                for cost, tuples in cost2assignments.iteritems():
                    if cost == defaultCost: continue
                    for t in tuples:
                        cOld.addTuple(t, cost)
        else:
            self.constraintBySignature[varIndices] = constraint
            wcsp.constraints.append(constraint)
        
        
    def gatherConstraintTuples(self, wcsp, varIndices, formula):
        '''
        Collects and evaluates all tuples that belong to the constraint
        given by a formula. In case of disjunctions and conjunctions,
        this is fairly efficient since not all combinations
        need to be evaluated. Returns a dictionary mapping the constraint
        costs to the list of respective variable assignments.
        ''' 
        log = logging.getLogger('wcsp')
        logic = self.mrf.mln.logic
#         log.info(str(formula) + ': ' + (str(formula.weight) if not formula.isHard else '(hard)'))
        
        # we can treat conjunctions and disjunctions fairly efficiently
        defaultProcedure = False
        conj = logic.isConjunctionOfLiterals(formula)
        disj = logic.isDisjunctionOfLiterals(formula)
        if not conj and not disj:
            defaultProcedure = True
        if not defaultProcedure:
            assignment = [0] * len(varIndices)
            children = []
            for lit in formula.iterLiterals():
                children.append(lit)
            pivot = None
            for gndLiteral in children:
                if isinstance(gndLiteral, Logic.TrueFalse):
                    if (pivot is None) or (conj and gndLiteral.value < pivot) or (not conj and gndLiteral.value > pivot):
                        pivot = gndLiteral.value
                    continue
                (gndAtom, varVal) = (gndLiteral, True) if isinstance(gndLiteral, Logic.GroundAtom) else (gndLiteral.gndAtom, not gndLiteral.negated)
                if not conj: varVal = not varVal
                varVal = 1 if varVal else 0
                varIdx = self.gndAtom2VarIndex[gndAtom]
                if varIdx in self.mutexVars:
                    if isinstance(gndLiteral, Logic.GroundLit) and varVal == 0:
                        defaultProcedure = True
                        break
                    varVal = self.varIdx2GndAtom[varIdx].index(gndAtom)
                assignment[varIndices.index(varIdx)] = varVal
            if not defaultProcedure:
                if formula.isHard and pivot is not None:
                    msg = 'No fuzzy truth values are allowed in hard constraints.'
                    log.exception(msg)
                    raise Exception(msg)
                if conj:
                    if formula.isHard:
                        cost = 0
                        defcost = WCSP.TOP
                    else:
                        pivot = pivot if pivot is not None else 1 
                        cost = formula.weight * (1 - pivot)
                        defcost = formula.weight
                else:
                    if formula.isHard:
                        cost = WCSP.TOP
                        defcost = 0
                    else:
                        pivot = pivot if pivot is not None else 0
                        defcost = 0
                        cost = formula.weight * (1 - pivot)
                return {cost: (assignment,), defcost: 'else'}
        if defaultProcedure: 
            # fallback: go through all combinations of truth assignments
            domains = [range(d) for i,d in enumerate(wcsp.domSizes) if i in varIndices]
#             log.warning(varIndices)
#             log.warning(domains)
            cost2assignments = {}
            for c in utils.combinations(domains):
                world = [0] * len(self.mrf.gndAtoms)
                for var, assignment in zip(varIndices, c):
                    if var in self.mutexVars: # mutex constraint
                        world[self.varIdx2GndAtom[var][assignment].idx] = 1
                    else:
                        world[self.varIdx2GndAtom[var][0].idx] = 1 if assignment > 0 else 0
                # the MRF feature imposed by this formula 
                truth = formula.isTrue(world)
                assert truth is not None
                assert not (truth > 0 and truth < 1 and formula.isHard)
#                 log.info(str(formula) + str(' %f' % truth))
                cost = WCSP.TOP if truth < 1 and formula.isHard else (1 - truth) * formula.weight
                assignments = cost2assignments.get(cost, [])
                cost2assignments[cost] = assignments
                assignments.append(c)
            return cost2assignments
        assert False # unreachable
        
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
        
    def getMostProbableWorldDB(self, verbose=False):
        '''
        Returns a Database object with the most probable truth assignment.
        '''
        log = logging.getLogger(self.__class__.__name__)
        wcsp = self.convert()
        solution, _ = wcsp.solve(verbose)
        if solution is None:
            log.exception('Knowledge base is unsatisfiable.')
        resultDB = Database(self.mln)
        resultDB.domains = dict(self.mrf.domains)
        resultDB.evidence = dict(self.mrf.getEvidenceDatabase())
        for varIdx, valIdx in enumerate(solution):
            if varIdx in self.mutexVars:
                for v in range(len(self.varIdx2GndAtom[varIdx])):
                    resultDB.evidence[str(self.varIdx2GndAtom[varIdx][v])] = 1 if (valIdx == v) else 0
            else:
                resultDB.evidence[str(self.varIdx2GndAtom[varIdx][0])] = 1 if (valIdx == 1) else 0
        return resultDB

    def getPseudoDistributionForGndAtom(self, gndAtom):
        '''
        Computes a relative "distribution" for all possible variable assignments of 
        a mutex constraint. This can be used to determine the confidence in particular
        most probable world by comparing the score with the second-most probable one.
        '''
        if isinstance(gndAtom, basestring):
            gndAtom = self.mrf.gndAtoms[gndAtom]
        
        if not isinstance(gndAtom, Logic.GroundAtom):
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
        

# for debugging only
if __name__ == '__main__':
    pass
#     mln = MLN('/home/nyga/code/prac/models/experimental/deep_sense/priors.mln')
#     db = Database(mln, '/home/nyga/code/prac/models/experimental/deep_sense/db/1.db')
#     mrf = mln.groundMRF(db)
#     
#     conv = WCSPConverter(mrf)
#     wcsp = conv.convert()
#     wcsp.write(sys.stdout)
#     solution = wcsp.solve()
#     for i, s in enumerate(solution):
#         print conv.varIdx2GndAtom[i][0], s, 
#         for ga in conv.varIdx2GndAtom[i]: print ga,
#         print
