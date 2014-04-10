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
from logic.common import Logic, Lit, GroundLit
import sys
import logging
import types
from utils.multicore import with_tracing
from multiprocessing.pool import Pool


# this readonly global is for multiprocessing to exploit copy-on-write
# on linux systems
global_bpllGrounding = None

# multiprocessing function
def compute_formula_statistics(formula):
    bpllStat = BPLLStatistics(global_bpllGrounding.mrf.evidence)#current_process().bpll_stats
    if global_bpllGrounding.mrf.mln.logic.isConjunctionOfLiterals(formula): # use the fast conjunction grounding
        for gndFormula in global_bpllGrounding.iterConjunctionGroundings(formula, formula.idx):
            global_bpllGrounding._computeStatisticsForGndFormula(gndFormula, formula.idx, bpllStat=bpllStat)
    else: # go through all ground formulas
        for gndFormula, _ in formula.iterGroundings(global_bpllGrounding.mrf, simplify=False):
            # get the set of block indices that the variables appearing in the formula correspond to
            global_bpllGrounding._computeStatisticsForGndFormula(gndFormula, formula.idx, bpllStat=bpllStat)
    return bpllStat


class BPLLStatistics(object):
    '''
    Wrapper class for encapsulation of the sufficient statistics
    for a BPLL learner. Mimics the behavior of an MRF wrt. temporary evidence.
    '''
    
    def __init__(self, evidence):
        self.fcounts = {}
#         self.blockRelevantFormulas = defaultdict(set)
        self.evidence = list(evidence)
        
    def _addMBCount(self, idxVar, size, idxValue, idxWeight,inc=1):
#         self.blockRelevantFormulas[idxVar].add(idxWeight)
        if idxWeight not in self.fcounts:
            self.fcounts[idxWeight] = {}
        d = self.fcounts[idxWeight]
        if idxVar not in d:
            d[idxVar] = [0] * size
        d[idxVar][idxValue] += inc
        
       
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
        self.evidence = list(self.mrf.evidence)
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

    
    def _addMBCount(self, idxVar, size, idxValue, idxWeight,inc=1):
        self.blockRelevantFormulas[idxVar].add(idxWeight)
        if idxWeight not in self.fcounts:
            self.fcounts[idxWeight] = {}
        d = self.fcounts[idxWeight]
        if idxVar not in d:
            d[idxVar] = [0] * size
        d[idxVar][idxValue] += inc
        
        
    def _computeStatisticsForGndFormula(self, gndFormula, idxFormula, bpllStat=None):
        # get the set of block indices that the variables appearing in the formula correspond to
        if bpllStat is None:
            bpllStat = self
        log = logging.getLogger(self.__class__.__name__)
        idxBlocks = set()
        for idxGA in gndFormula.idxGroundAtoms():
            idxBlocks.add(self.mrf.atom2BlockIdx[idxGA])
        for idxVar in idxBlocks:
            (idxGA, block) = self.mrf.pllBlocks[idxVar]
            if idxGA is not None: # ground atom is the variable as it's not in a block
                # check if formula is true if gnd atom maintains its truth value
                truth = gndFormula.isTrue(bpllStat.evidence)
                if truth:
                    bpllStat._addMBCount(idxVar, 2, 0, idxFormula, inc=truth)
                # check if formula is true if gnd atom's truth value is inverted
                old_tv = bpllStat.evidence[idxGA]
                bpllStat.evidence[idxGA] =  1 - old_tv
                truth = gndFormula.isTrue(bpllStat.evidence)
                if truth:
                    bpllStat._addMBCount(idxVar, 2, 1, idxFormula, inc=truth)
                bpllStat.evidence[idxGA] = old_tv
            else: # the block is the variable (idxGA is None)
                size = len(block)
                idxGATrueone = block[self.evidenceIndices[idxVar]]
                # check true groundings for each block assigment
                evidence_backup = dict([(idx, bpllStat.evidence[idx]) for idx in block])
                for idxValue, idxGA in enumerate(block):
                    if idxGA != idxGATrueone:
                        bpllStat.evidence[idxGATrueone] = 0
                        bpllStat.evidence[idxGA] = 1
                    truth = gndFormula.isTrue(bpllStat.evidence)
                    if truth:
                        bpllStat._addMBCount(idxVar, size, idxValue, idxFormula, inc=truth)
                    for idx, val in evidence_backup.iteritems():
                        bpllStat.evidence[idx] = val
    
    
    def iterConjunctionGroundings(self, formula, idxFormula):
        '''
        Recursively generate the groundings of a conjunction that do _not_
        have a definite truth value yet given the evidence.
        '''
        log = logging.getLogger(self.__class__.__name__)
        logic = self.mrf.mln.logic
        # make a copy of the formula to avoid side effects
        formula = formula.ground(self.mrf, {}, allowPartialGroundings=True)
        conjunction_ = logic.conjunction([formula, logic.truefalse(1)]) if not hasattr(formula, 'children') else formula
        # make equality constraints access their variable domains
        # this is a _really_ dirty hack but it does the job ;-)
        variables = conjunction_.getVariables(self.mrf.mln)
        def getEqualityVariables(self, mln):
            var2dom = {}
            for c in self.params:
                if mln.logic.isVar(c):
                    var2dom[c] = variables[c]
            return var2dom 
        # rearrange children
        children = list(conjunction_.children)
        conj = []
        for child in list(children):
            if isinstance(child, Logic.Equality):
                conj.append(child)
                children.remove(child)
                # replace the getVariables method in this equality instance
                # by our customized one from above
                setattr(child, 'getVariables', types.MethodType(getEqualityVariables, child))
        for child in list(children):
            predName = None
            if isinstance(child, Lit):
                predName = child.predName
            elif isinstance(child, GroundLit):
                predName = child.gndAtom.predName
            if predName in self.mrf.mln.blocks: 
                conj.append(child)
                children.remove(child)
#         raise Exception('assert')
        conj.extend(children)
        conj = logic.conjunction(conj)
        for gndFormula in self._iterConjunctionGroundings(conj, 0, len(conj.children), self.mrf, {}, strict=False, idxFormula=idxFormula):
            yield gndFormula
            
            
    def _iterConjunctionGroundings(self, formula, litIdx, numChildren, mrf, assignment, strict, idxFormula):
        log = logging.getLogger(self.__class__.__name__)
        if litIdx == numChildren:
            gndFormula = formula.ground(mrf, assignment, simplify=False)
            gndFormula.fIdx = idxFormula
#             self._computeStatisticsForGndFormula(gndFormula, idxFormula)
            yield gndFormula
            return
        lit = formula.children[litIdx]
        for varAssignment in lit.iterTrueVariableAssignments(mrf, mrf.evidence, truthThreshold=.0, strict=True if isinstance(lit, Logic.Equality) else strict, includeUnknown=True, partialAssignment=assignment):
            if varAssignment == {}:
                if len(set(lit.getVariables(mrf.mln).keys()).difference(set(assignment.keys()))) > 0:
                    return
                truth = lit.ground(mrf, assignment).isTrue(mrf.evidence)
                if truth == 0:
                    if strict: 
                        return
                    strict = True
            assignment = dict(assignment)
            assignment.update(varAssignment)
            for gf in self._iterConjunctionGroundings(formula, litIdx+1, numChildren, mrf, assignment, strict=strict, idxFormula=idxFormula):
                yield gf
                
                
    def _computeStatistics(self): 
        global global_bpllGrounding
        log = logging.getLogger(self.__class__.__name__)
        self.createVariablesAndEvidence()
        mrf = self.mrf
        multiCPU = self.params.get('useMultiCPU', False)
        if multiCPU:
            for i, f in enumerate(mrf.formulas): f.idx = i
            global_bpllGrounding = self
            pool = Pool()
            log.info('Multiprocessing enabled using %d cores.' % pool._processes)
            try:
                bpll_statistics = pool.map(with_tracing(compute_formula_statistics), mrf.formulas)
                for bpll_stat in bpll_statistics:
                    # update the statistics
                    for fIdx, var2val in bpll_stat.fcounts.iteritems():
                        for var, values in var2val.iteritems():
                            for valIdx, val in enumerate(values):
                                self._addMBCount(var, len(values), valIdx, fIdx, val)
            except Exception, e:
                pool.terminate()
                pool.join()
                raise e
        else:
            for idxFormula, formula in enumerate(mrf.formulas):
                sys.stdout.write('%d/%d    \r' % (idxFormula, len(mrf.formulas)))
                sys.stdout.flush()
                if self.mrf.mln.logic.isConjunctionOfLiterals(formula):
                    for gndFormula in self.iterConjunctionGroundings(formula, idxFormula):
                        self._computeStatisticsForGndFormula(gndFormula, idxFormula)
                else:
                    # go through all ground formulas
                    for gndFormula, _ in formula.iterGroundings(mrf, simplify=False):
                        # get the set of block indices that the variables appearing in the formula correspond to
                        self._computeStatisticsForGndFormula(gndFormula, idxFormula)
                    
    def _createGroundFormulas(self):
        '''
        We will not create ground formula and keep them in memory but
        throw them away after we have collected its sufficient statistics.
        So we override the default grounding at this place.
        '''
#         log = logging.getLogger(self.__class__.__name__)
#         log.info('createGroundFormulas()')
        pass


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# here comes some very experimental code. which is currently not in use.


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


