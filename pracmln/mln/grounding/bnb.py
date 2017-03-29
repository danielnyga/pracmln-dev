# Markov Logic Networks - Intelligent Grounding for Branch-and-Bound-Search
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

from pracmln.utils.undo import Ref, Number, List, ListDict, Boolean
from pracmln.logic.common import Logic
from pracmln.mln.util import unifyDicts


class FormulaGrounding(object):
    """
    Represents a particular (partial) grounding of a formula with respect to _one_ predicate
    and in terms of disjoint sets of variables occurring in that formula. A grounding of
    the formula is represented as a list of assignments of the independent variable sets.
    It represents a node in the search tree for weighted SAT solving.
    Additional fields:
    - depth:    the depth of this formula grounding (node) in the search tree
                The root node (the formula with no grounded variable has depth 0.
    - children: list of formula groundings that have been generate from this fg.
    """ 

    def __init__(self, formula, mrf, parent=None, assignment=None):
        """
        Instantiates the formula grounding for a given
        - formula:    the formula grounded in this node
        - mrf:        the MRF associated to this problem
        - parent:     the formula grounding this fg has been created from
        - assignment: dictionary mapping variables to their values
        """
        self.mrf = mrf
        self.formula = formula
        self.parent = Ref(parent)
        self.costs = Number(0.)
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
            for (v, d) in parent.domains.items():
                self.domains.extend(v, list(d))
        self.domains.epochEndsHere()
                
    def epochEndsHere(self):
        for mem in (self.parent, self.costs, self.children, self.domains, self.processed):
            mem.epochEndsHere()
        
    def undoEpoch(self):
        for mem in (self.parent, self.costs, self.children, self.domains, self.processed):
            mem.undoEpoch()
            
    def countGroundings(self):
        """
        Computes the number of ground formulas subsumed by this FormulaGrounding
        based on the domain sizes of the free (unbound) variables.
        """
        gf_count = 1
        for var in self.formula.getVariables(self.mrf):
            domain = self.mrf.domains[self.formula.getVarDomain(var, self.mrf)]
            gf_count *= len(domain)
        return gf_count
    
    def ground(self, assignment=None):
        """
        Takes an assignment of _one_ particular variable and
        returns a new FormulaGrounding with that assignment. If
        the assignment renders the formula false or true, then
        the costs are returned.
        """
        # calculate the number of ground formulas resulting from
        # the remaining set of free variables
        if assignment is None:
            assignment = {}
        gf_count = 1
#         print self
        for var in set(self.formula.getVariables(self.mrf.mln)).difference(list(assignment.keys())):
            domain = self.domains[var]
            if domain is None: return 0.
            gf_count *= len(domain)
        gf = self.formula.ground(self.mrf, assignment, allowPartialGroundings=True, simplify=True)
        gf.weight = self.formula.weight
        for var_name, val in assignment.items(): break
        self.domains.drop(var_name, val)
        # if the simplified gf reduces to a TrueFalse instance, then
        # we return the costs if it's false, or 0 otherwise.
        if isinstance(gf, Logic.TrueFalse):
            if gf.value: costs = 0.0
            else:
                costs = self.formula.weight * gf_count
            self.costs += costs
            return costs
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


class GroundingFactory(object):
    """
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
    - depth2fgs   mapping from a depth of the search tree to the corresponding list 
                  of FormulaGroundings
    - vars_processed    list of variable names that have already been processed so far
    - values_processed    mapping from a variable name to the list of values of that vaiable that
                          have already been assigned so far.
    This class maintains a stack of all its fields in order allow undoing groundings
    that have been performed once.
    """
    
    def __init__(self, formula, mrf):
        """
        formula might be a formula or a FormulaGrounding instance.
        """
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
        """
        Expects a ground atom and creates all groundings 
        that can be derived by it in terms of FormulaGroundings.
        """
        self.manipulatedFgs.clear()
        # get all variable assignments of matching literals in the formula 
        var_assignments = {}
        for lit in self.formula.iterLiterals():
            assignment = self.gndAtom2Assignment(lit, gndAtom)
            if assignment is not None:
                unifyDicts(var_assignments, assignment)
        cost = .0
        
        # first evaluate formula groundings that contain 
        # this gnd atom as an artifact
        min_depth = None
        min_depth_fgs = []
        for fg in self.gndAtom2fgs.get(gndAtom, []):
            if len(self.variable_stack) <= fg.depth:
                continue
            if fg.processed.value:
#                 print fg.parent.obj.formula, '->', fg.formula, 'has already been processed'
                continue
#             print 'artifact', fg
            truth = fg.formula.isTrue(self.mrf.evidence)
            if truth is not None:
                cost -= fg.costs.value
#                 print fg, 'is', truth
                if not fg in self.manipulatedFgs:
                    self.manipulatedFgs.append(fg)
                fg.processed.set(True)
#                 if self.var2fgs.contains(self.variable_stack[fg.depth], fg):
                self.var2fgs.drop(self.variable_stack[fg.depth], fg)
#                 if fg in fg.parent.obj.children:
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
#             if not fg.formula.isTrue(fg.mrf.evidence):
            if fg.formula.isTrue(fg.mrf.evidence) == False:
#                 numGroundings = fg.countGroundings()
#                 print fg.formula, '%d x %.2f' % (numGroundings, fg.formula.weight)
                cost += fg.formula.weight * fg.countGroundings()
                fg.costs.set(cost)
        # straighten up the variable stack and formula groundings
        # since they might have become empty
        for var in list(self.variable_stack):
            if self.var2fgs[var] is None:
                self.variable_stack.remove(var)
        for var, value in var_assignments.items():
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
                    for varNotInTree in [v for v in list(self.values_processed.keys()) if v not in self.variable_stack]: break
                    if varNotInTree is None: continue
                    values = self.values_processed[varNotInTree]
                    for v in values:
                        vars_and_values.append({varNotInTree: v})
                for var_value in vars_and_values:
                    for var_name, val in var_value.items(): break
#                     print fg.domains, 'contains', var_name, val, ':',fg.domains.contains(var_name, val) 
                    if not fg.domains.contains(var_name, val): continue
#                     print 'grounding', var_value
                    gnd_result = fg.ground(var_value)
#                     self.printTree()
#                     print gnd_result
                    if not fg in self.manipulatedFgs:
                        self.manipulatedFgs.append(fg)
#                     print gnd_result
                    # if the truth value of a grounding cannot be determined...
                    if isinstance(gnd_result, FormulaGrounding):
                        # collect all ground atoms that have been created as 
                        # as artifacts for future evaluation
                        artifactGndAtoms = []
                        gnd_result.formula.getGroundAtoms(artifactGndAtoms)
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
        print('---')
        while len(queue) > 0:
            n = queue.pop()
            space = ''
            for _ in range(n.depth): space += '--'
            print(space + str(n))
            queue.extend(n.children.list)
        print('---')
        
    def gndAtom2Assignment(self, lit, atom):
        """
        Returns None if the literal and the atom do not match.
        """
        if type(lit) is Logic.Equality or lit.predName != atom.predName: return None
        assignment = {}
        for p1, p2 in zip(lit.params, atom.params):
            if self.mrf.mln.logic.isVar(p1):
                assignment[p1] = p2
            elif p1 != p2: return None
        return assignment
    