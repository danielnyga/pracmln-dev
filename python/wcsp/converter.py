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

from wcsp import WCSP
from wcsp import Constraint
import utils
from praclog import logging
from logic.common import Logic
from mln.database import Database
import copy
from mln.atomicblocks import MutexBlock, SoftMutexBlock
import sys



class WCSPConverter(object):
    '''
    Class for converting an MLN into a WCSP problem for efficient
    MPE inference.
    '''
    
    def __init__(self, mrf):
        self.mrf = mrf
        self.gndAtom2AtomicBlock = {}
        self.createVariables()
        self.constraintBySignature = {}
    
    
    def createVariables(self):
        '''
        Create the variables, one binary for each ground atom.
        Considers also mutually exclusive blocks of ground atoms.
        '''
        blocks = copy.deepcopy(self.mrf.gndAtomicBlocks)
        self.variables = []
        self.gndAtom2AtomicBlock = {}
        for atomicBlock in blocks.values():
            newAtomicBlock = copy.copy(atomicBlock)
            newAtomicBlock.gndatoms = []
            for gndatom in atomicBlock.gndatoms:
                if self.mrf.evidence[gndatom.idx] != None:
                    continue
                newAtomicBlock.gndatoms.append(gndatom)
            newAtomicBlock.idx2val = {}
            newAtomicBlock.val2idx = {}
            evidence = dict([(atom.idx, self.mrf.evidence[atom.idx]) for atom in atomicBlock.gndatoms if self.mrf.evidence[atom.idx] != None])
            for idx, value in enumerate(newAtomicBlock.generateValueTuples(evidence)):
                newAtomicBlock.idx2val[idx] = value
                newAtomicBlock.val2idx[value] = idx
            if len(newAtomicBlock.idx2val) >= 1:
                newAtomicBlock.blockidx = len(self.variables)
                self.variables.append(newAtomicBlock)
                for gndatom in newAtomicBlock.gndatoms:
                    self.gndAtom2AtomicBlock[gndatom.idx] = newAtomicBlock

    
    def convert(self):
        '''
        Performs a conversion from an MLN into a WCSP.
        '''
        wcsp = WCSP()
        wcsp.domSizes = [len(block.idx2val) for block in self.variables]
        log = logging.getLogger(self.__class__.__name__)
        mln = self.mrf.mln
        logic = mln.logic
        # preprocess the ground formulas
        gfs = []
        for gf in self.mrf.gndFormulas:
            gf.weight = mln.formulas[gf.idxFormula].weight
            gf.isHard = mln.formulas[gf.idxFormula].isHard
            if gf.weight == 0 and not gf.isHard:
                continue
            if gf.weight < 0:
                f = logic.negation([gf])
                f.weight = abs(gf.weight)
                f.isHard = gf.isHard
            else: f = gf
            f_ = f.simplify(self.mrf)
            if isinstance(f_, Logic.TrueFalse) or gf.weight == 0 and not gf.isHard:
                continue
            f_ = f_.toNNF()
            f_.weight = f.weight
            f_.isHard = f.isHard
            gfs.append(f_)
        for f in gfs:
            self.generateConstraint(wcsp, f)
        return wcsp


    def generateConstraint(self, wcsp, wf):
        '''
        Generates and adds a constraint from a given weighted formula.
        '''
        #log = logging.getLogger('wcsp')
        idxGndAtoms = wf.idxGroundAtoms()
        varIndices = set(map(lambda x: self.gndAtom2AtomicBlock[x].blockidx, idxGndAtoms))
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
        log = logging.getLogger(self.__class__.__name__)
        logic = self.mrf.mln.logic
        # we can treat conjunctions and disjunctions fairly efficiently
        defaultProcedure = False
        conj = logic.isConjunctionOfLiterals(formula)
        disj = logic.isDisjunctionOfLiterals(formula)
        if not conj and not disj:
            defaultProcedure = True
        if not defaultProcedure:
            assignment = [0] * len(varIndices)
            children = list(formula.iterLiterals())
            pivot = None
            for gndLiteral in children:
                if isinstance(gndLiteral, Logic.TrueFalse):
                    if (pivot is None) or (conj and gndLiteral.value < pivot) or (not conj and gndLiteral.value > pivot):
                        pivot = gndLiteral.value
                    continue
                (gndAtom, varVal) = (gndLiteral, True) if isinstance(gndLiteral, Logic.GroundAtom) else (gndLiteral.gndAtom, not gndLiteral.negated)
                if not conj: varVal = not varVal
                varVal = 1 if varVal else 0
                
                block = self.gndAtom2AtomicBlock[gndAtom.idx]
                if isinstance(block, MutexBlock) or isinstance(block, SoftMutexBlock):
                    if isinstance(gndLiteral, Logic.GroundLit) and varVal == 0:
                        defaultProcedure = True
                        break
                    varVal = block.gndatoms.index(gndAtom)
                assignment[varIndices.index(block.blockidx)] = varVal
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
            domains = [list(b.generateValueTuples()) for b in self.variables if b.blockidx in varIndices]
            cost2assignments = {}
            # compute number of worlds to be examined and print a warning
            # if it exceeds 10,000 poss. worlds
            worlds = 1
            for d in domains:
                worlds *= len(d)
            if worlds > 1000000:
                log.warning('!!! WARNING: %d POSSIBLE WORLDS ARE GOING TO BE EVALUATED. KEEP IN SIGHT YOUR MEMORY CONSUMPTION !!!' % worlds)
            for c in utils.combinations(domains):
                world = [0] * len(self.mrf.gndAtoms)
                valIndices = []
                for var, assignment in zip(varIndices, c):
                    valIndices.append(self.variables[var].val2idx[assignment])
                    for atom, val in zip(self.variables[var].gndatoms, assignment):
                        world[atom.idx] = val
                # the MRF feature imposed by this formula 
                truth = formula.isTrue(world)
                assert truth is not None
                assert not (truth > 0 and truth < 1 and formula.isHard)
                cost = WCSP.TOP if (truth < 1 and formula.isHard) else (1 - truth) * formula.weight
                assignments = cost2assignments.get(cost, [])
                cost2assignments[cost] = assignments
                assignments.append(valIndices)
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
        resultDB = Database(self.mrf.mln)
        resultDB.domains = dict(self.mrf.domains)
        resultDB.evidence = dict(self.mrf.getEvidenceDatabase())
        for varIdx, valIdx in enumerate(solution):
            block = self.variables[varIdx]
            values = block.idx2val[valIdx]
            for atom, val in zip(block.gndatoms, values):
                resultDB.evidence[str(atom)] = val
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
