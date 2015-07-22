# Weighted Constraint Satisfaction Problems -- MPE inference on MLNs
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

from mln.util import fstr, combinations, dict_union, ifNone, Interval, out
from mln.inference.inference import Inference
from wcsp import Constraint
from wcsp import WCSP
from logic.common import Logic
from mln.database import Database
import copy
from mln.mrfvars import MutexVariable, SoftMutexVariable, FuzzyVariable
import logging
from collections import defaultdict
from mln.grounding.default import DefaultGroundingFactory
from mln.constants import infty, HARD
from mln.grounding.fastconj import FastConjunctionGrounding


logger = logging.getLogger(__name__)


class WCSPInference(Inference):
    
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)
        self.converter = WCSPConverter(self.mrf)
        
    
    def _run(self):
        result_ = {}
        result = self.result_dict(verbose=self.verbose)
        for query in self.queries:
            query = str(query)
            result_[query] = result[query] if query in result else self.mrf[query] 
        return result_
    
    
    def result_dict(self, verbose=False):
        '''
        Returns a Database object with the most probable truth assignment.
        '''
        wcsp = self.converter.convert()
        solution, _ = wcsp.solve()
        if solution is None:
            raise Exception('MLN is unsatisfiable.')
        result = {}
        for varidx, validx in enumerate(solution):
            value = self.converter.domains[varidx][validx]
            result.update(self.converter.variables[varidx].value2dict(value))
        return dict([(str(self.mrf.gndatom(idx)), val) for idx, val in result.iteritems()])



class WCSPConverter(object):
    '''
    Class for converting an MLN into a WCSP problem for efficient
    MPE inference.
    '''
    
    
    def __init__(self, mrf, verbose=False, multicore=False):
        self.mrf = mrf
        self.constraints = {} # mapping the signature of a constaint to its constraint object
        self.verbose = verbose
        self._createvars()
        self.wcsp = WCSP()
        self.wcsp.domsizes = [len(self.domains[i]) for i in self.variables]
        self.multicore = multicore
    
    
    def _createvars(self):
        '''
        Create the variables, one binary for each ground atom.
        Considers also mutually exclusive blocks of ground atoms.
        '''
        self.variables = {} # maps an index to its MRF variable
        self.domains = defaultdict(list) # maps a var index to a list of its MRF variable value tuples
        self.atom2var = {} # maps ground atom indices to their variable index
        self.val2idx = defaultdict(dict)
        varidx = 0
        for variable in self.mrf.variables:
            if isinstance(variable, FuzzyVariable): # fuzzy variables are not subject to reasoning
                continue
            if variable.valuecount(self.mrf.evidence_dicti()) == 1: # the var is fully determined by the evidence
                continue
            self.variables[varidx] = variable
            for gndatom in variable.gndatoms:
                self.atom2var[gndatom.idx] = varidx
            for validx, (_, value) in enumerate(variable.itervalues(self.mrf.evidence_dicti())):
                self.domains[varidx].append(value)
                self.val2idx[varidx][value] = validx
            varidx += 1

    
    def convert(self):
        '''
        Performs a conversion from an MLN into a WCSP.
        '''
        # mln to be restored after inference
        self._weights = list(self.mrf.mln.weights)
        mln = self.mrf.mln
        logic = mln.logic
        # preprocess the formulas
        formulas = []
        for f in self.mrf.formulas:
            if f.weight == 0: 
                continue
            if f.weight < 0:
                f = logic.negate(f)
                f.weight = -f.weight
            formulas.append(f.nnf())
        # preprocess the ground formulas
#         grounder = DefaultGroundingFactory(self.mrf, formulas)
        grounder = FastConjunctionGrounding(self.mrf, formulas, multicore=self.multicore)
        for gf in grounder.itergroundings(simplify=True):
            if isinstance(gf, Logic.TrueFalse): 
                if gf.weight == HARD:
                    raise Exception('MLN is unsatisfiable: hard constraint %s violated' % self.mrf.mln.formulas[gf.idx])
                else:# formula is rendered true/false by the evidence -> equal in every possible world 
                    continue
#             gf = gf.nnf()
#             gf.print_structure(self.mrf.evidence)
            self.generate_constraint(gf)
        out(len(self.mrf.mln.weights), len(self._weights))
        self.mrf.mln.weights = self._weights
        return self.wcsp


    def generate_constraint(self, wf):
        '''
        Generates and adds a constraint from a given weighted formula.
        '''
        varindices = tuple(map(lambda x: self.atom2var[x], wf.gndatom_indices()))
        # collect the constraint tuples
        cost2assignments = self._gather_constraint_tuples(varindices, wf)
        if cost2assignments is None:
            return
        defcost = max(cost2assignments, key=lambda x: infty if cost2assignments[x] == 'else' else len(cost2assignments[x]))
        del cost2assignments[defcost] # remove the default cost values
        
        constraint = Constraint(varindices, defcost=defcost)
        constraint.defcost = defcost
        for cost, tuples in cost2assignments.iteritems():
            for t in tuples:
                constraint.tuple(t, cost)
        self.wcsp.constraint(constraint)
        
        
    def _gather_constraint_tuples(self, varindices, formula):
        '''
        Collects and evaluates all tuples that belong to the constraint
        given by a formula. In case of disjunctions and conjunctions,
        this is fairly efficient since not all combinations
        need to be evaluated. Returns a dictionary mapping the constraint
        costs to the list of respective variable assignments.
        ''' 
        logic = self.mrf.mln.logic
        # we can treat conjunctions and disjunctions fairly efficiently
        defaultProcedure = False
        conj = logic.islitconj(formula)
        disj = False
        if not conj:
            disj = logic.isclause(formula)
        if not varindices:
            return None
        if not conj and not disj:
            defaultProcedure = True
        if not defaultProcedure:
            assignment = {}#[0] * len(varindices)
            children = list(formula.literals())
            for gndlit in children:
                (gndatom, val) = (gndlit.gndatom, not gndlit.negated)
                if disj: val = not val
                val = 1 if val else 0
                variable = self.variables[self.atom2var[gndatom.idx]]
                tmp_evidence = dict_union(variable.value2dict(variable.evidence_value()), {gndatom.idx: val})
                if variable.valuecount(tmp_evidence) > 1:
                    defaultProcedure = True
                    break
                for _, value in variable.itervalues(tmp_evidence):
                    varidx = self.atom2var[gndatom.idx] 
                    validx = self.val2idx[varidx][value]
                # if the formula is unsatisfiable
                if assignment.get(varidx) is not None and assignment[varidx] != value:
                    if formula.weight == HARD:
                        raise Exception('Knowledge base is unsatisfiable.')
                    else: # for soft constraints, unsatisfiable formulas can be ignored
                        return None
                assignment[varidx] = validx
            if not defaultProcedure:
                maxtruth = formula.maxtruth(self.mrf.evidence)
                mintruth = formula.mintruth(self.mrf.evidence)
                if formula.weight == HARD and maxtruth in Interval(']0,1[') or mintruth in Interval(']0,1['):
                    raise Exception('No fuzzy truth values are allowed in hard constraints.')
                if conj:
                    if formula.weight == HARD:
                        cost = 0
                        defcost = self.wcsp.top
                    else:
                        cost = formula.weight * (1 - maxtruth)
                        defcost = formula.weight
                else:
                    if formula.weight == HARD:
                        cost = self.wcsp.top
                        defcost = 0
                    else:
                        defcost = 0
                        cost = formula.weight * (1 - mintruth)
                if len(assignment) != len(varindices):
                    raise Exception('Illegal variable assignments. Variables: %s, Assignment: %s' % (varindices, assignment))
                assignment = [assignment[v] for v in varindices]
                return {cost: [tuple(assignment)], defcost: 'else'}
        if defaultProcedure: 
            # fallback: go through all combinations of truth assignments
            domains = [self.domains[v] for v in varindices]
            cost2assignments = defaultdict(list)
            # compute number of worlds to be examined and print a warning
            worlds = 1
            for d in domains: worlds *= len(d)
            if worlds > 1000000:
                logger.warning('!!! WARNING: %d POSSIBLE WORLDS ARE GOING TO BE EVALUATED. KEEP IN SIGHT YOUR MEMORY CONSUMPTION !!!' % worlds)
            for c in combinations(domains):
                world = [0] * len(self.mrf.gndatoms)
                assignment = []
                for varidx, value in zip(varindices, c):
                    world = self.variables[varidx].setval(value, world)
                    assignment.append(self.val2idx[varidx][value])
                # the MRF feature imposed by this formula 
                truth = formula(world)
                if truth is None:
                    print 'POSSIBLE WORLD:'
                    print '==============='
                    self.mrf.print_world_vars(world)
                    print 'GROUND FORMULA:'
                    print '==============='
                    formula.print_structure(world)
                    raise Exception('Something went wrong: Truth of ground formula cannot be evaluated (see above)')
                
                if truth in Interval(']0,1[') and formula.weight == HARD:
                    raise Exception('No fuzzy truth values are allowed in hard constraints.')
                
                cost = self.wcsp.top if (truth < 1 and formula.weight == HARD) else (1 - truth) * formula.weight
                cost2assignments[cost].append(tuple(assignment))
            return cost2assignments
        assert False # unreachable
        
        
    def forbid_gndatom(self, atom, truth=True):
        '''
        Adds a unary constraint that prohibits the given ground atom
        being true.
        '''
        atomidx = atom if type(atom) is int else (self.mrf.gndatom(atom).idx if type(atom) is str else atom.idx)
        varidx = self.atom2var[atomidx]
        variable = self.variables[varidx]
        evidence = list(self.mrf.evidence)
        evidence[atomidx] = {True: 1, False: 0}[truth]
        c = Constraint((varidx,))
        for _, value in variable.itervalues(evidence):
            validx = self.val2idx[varidx][value]
            c.tuple((validx,), self.wcsp.top)
        self.wcsp.constraint(c)
        
        
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
        