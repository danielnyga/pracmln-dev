# FUZZY LOGIC
#
# (C) 2012-2013 by Daniel Nyga (nyga@cs.tum.edu)
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

from fol import FirstOrderLogic
from common import Logic, logic_factory
import logging


class FuzzyLogic(Logic):
    '''
    Implementation of fuzzy logic for MLNs.
    '''


    @staticmethod
    def min_undef(*args):
        '''
        Custom minimum function return None if one of its arguments
        is None and min(*args) otherwise.
        '''
        if len(filter(lambda x: x == 0, args)) > 0:
            return 0
        return reduce(lambda x, y: None if (x is None or y is None) else min(x, y), *args)
    
    @staticmethod
    def max_undef(*args):
        '''
        Custom maximum function return None if one of its arguments
        is None and max(*args) otherwise.
        '''
        if len(filter(lambda x: x == 1, args)) > 0:
            return 1
        return reduce(lambda x, y: None if x is None or y is None else max(x, y), *args)
    
    
    class Constraint(FirstOrderLogic.Constraint): pass
    class Formula(FirstOrderLogic.Formula): pass
    class ComplexFormula(FirstOrderLogic.Formula): pass
    
    
    class Lit(FirstOrderLogic.Lit):
        
        def simplify(self, mrf):
            if any(map(self.logic.isVar, self.params)):
                return self.logic.lit(self.negated, self.predName, self.params)
            s = "%s(%s)" % (self.predName, ",".join(self.params))
            truth = mrf.gndAtoms[s].isTrue(mrf.evidence)
            if truth is None:
                return self
            else:
                if self.negated: truth = 1 - truth
                return self.logic.true_false(truth)
    
    
    class GroundLit(FirstOrderLogic.GroundLit):
        
        def isTrue(self, world_values):
            truth = self.gndAtom.isTrue(world_values)
            if truth is None: return None
            return (1 - truth) if self.negated else truth 
    
        def simplify(self, mrf):
            f = self.gndAtom.simplify(mrf)
            if isinstance(f, Logic.TrueFalse):
                if self.negated:
                    return f.invert()
                else:
                    return f
            return self.logic.gnd_lit(self.gndAtom, self.negated)
        
        
    class GroundAtom(FirstOrderLogic.GroundAtom):
        
        def isTrue(self, world_values):
            val = world_values[self.idx]
            if val is None: return None
            return val
        
        def simplify(self, mrf):
            truth = mrf.evidence[self.idx]
            if truth is None:
                return self
            return self.logic.true_false(truth)
    
    
    class Negation(FirstOrderLogic.Negation):
        
        def isTrue(self, world_values):
            val = self.children[0].isTrue(world_values)
            return None if val is None else 1. - val
        
        def simplify(self, mrf):
            f = self.children[0].simplify(mrf)
            if isinstance(f, Logic.TrueFalse):
                return f.invert()
            else:
                return self.logic.negation([f])
    
    class Conjunction(FirstOrderLogic.Conjunction):
        
        def isTrue(self, world_values):
            return FuzzyLogic.min_undef(map(lambda a: a.isTrue(world_values), self.children))
        
        def simplify(self, mrf):
            sf_children = []
            minTruth = None
            for child_ in self.children:
                child = child_.simplify(mrf)
#                 logging.getLogger().info('%s %s is %s (%s)' % (str(type(child_)), child_, child, child.__class__.__name__))
                if isinstance(child, Logic.TrueFalse):
                    truth = child.isTrue()
                    if truth == 0:
                        return self.logic.true_false(0.)
                    if minTruth is None or truth < minTruth:
                        minTruth = truth
                else:
                    sf_children.append(child)
            if minTruth is not None and minTruth < 1 or minTruth == 1 and len(sf_children) == 0:
                sf_children.append(self.logic.true_false(minTruth))
    #             logging.getLogger().info(sf_children)
            if len(sf_children) > 1:
                return self.logic.conjunction(sf_children)
            elif len(sf_children) == 1:
                return sf_children[0]
            else:
                assert False # should be unreachable
    
    
    class Disjunction(FirstOrderLogic.Disjunction):
        
        def isTrue(self, world_values):
            return FuzzyLogic.max_undef(map(lambda a: a.isTrue(world_values), self.children))
    
        def simplify(self, mrf):
            sf_children = []
            maxTruth = None
            for child in self.children:
                child = child.simplify(mrf)
                if isinstance(child, Logic.TrueFalse):
                    truth = child.isTrue()
                    if truth == 1:
                        return self.logic.true_false(1.)
                    if maxTruth is None or truth > maxTruth:
                        maxTruth = truth
                else:
                    sf_children.append(child)
            if maxTruth is not None and maxTruth > 0 or (maxTruth == 0 and len(sf_children) == 0):
                sf_children.append(self.logic.true_false(maxTruth))
            if len(sf_children) > 1:
                return self.logic.disjunction(sf_children)
            elif len(sf_children) == 1:
                return sf_children[0]
            else:
                assert False
            
    
    class Implication(FirstOrderLogic.Implication):
        
        def isTrue(self, world_values):
            ant = self.children[0].isTrue(world_values)
            return FuzzyLogic.max_undef([None if ant is None else 1. - ant, self.children[1].isTrue(world_values)])
    
        def simplify(self, mrf):
            return self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]]).simplify(mrf)
        
        
    class Biimplication(FirstOrderLogic.Biimplication):
        
        def isTrue(self, world_values):
            return FuzzyLogic.min_undef([self.children[0].isTrue(world_values), self.children[1].isTrue(world_values)])
    
        def simplify(self, mrf):
            c1 = self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]])
            c2 = self.logic.disjunction([self.children[0], self.logic.negation([self.children[1]])])
            return self.logic.conjunction([c1,c2]).simplify(mrf)
        
        
    class Equality(FirstOrderLogic.Equality):
        
        def isTrue(self, world_values=None):
            if any(map(self.logic.isVar, self.params)):
                return None
            equals = 1. if (self.params[0] == self.params[1]) else 0.
            return (1. - equals) if self.negated else equals
        
        def simplify(self, mrf):
            truth = self.isTrue(mrf.evidence) 
            if truth != None: return self.logic.true_false(truth)
            return self.logic.equality(list(self.params), negated=self.negated)
        
    class TrueFalse(Formula, FirstOrderLogic.TrueFalse):
        
        def __init__(self, value):
            assert value >= 0. and value <= 1.
            self.value = value
        
        def __str__(self):
            return str(self.value)
        
        def cstr(self, color=False):
            return str(self)
        
        def invert(self):
            return self.logic.true_false(1. - self.value)
    
    class Exist(FirstOrderLogic.Exist, Logic.ComplexFormula):
        pass

    @logic_factory
    def conjunction(self, *args, **kwargs):
        return FuzzyLogic.Conjunction(*args, **kwargs)
    
    @logic_factory 
    def disjunction(self, *args, **kwargs):
        return FuzzyLogic.Disjunction(*args, **kwargs)
    
    @logic_factory
    def negation(self, *args, **kwargs):
        return FuzzyLogic.Negation(*args, **kwargs)
    
    @logic_factory 
    def implication(self, *args, **kwargs):
        return FuzzyLogic.Implication(*args, **kwargs)
    
    @logic_factory
    def biimplication(self, *args, **kwargs):
        return FuzzyLogic.Biimplication(*args, **kwargs)
    
    @logic_factory
    def equality(self, *args, **kwargs):
        return FuzzyLogic.Equality(*args, **kwargs)
     
    @logic_factory
    def exist(self, *args, **kwargs):
        return FuzzyLogic.Exist(*args, **kwargs)
    
    @logic_factory
    def gnd_atom(self, *args, **kwargs):
        return FuzzyLogic.GroundAtom(*args, **kwargs)
    
    @logic_factory
    def lit(self, *args, **kwargs):
        return FuzzyLogic.Lit(*args, **kwargs)
    
    @logic_factory
    def gnd_lit(self, *args, **kwargs):
        return FuzzyLogic.GroundLit(*args, **kwargs)
    
    @logic_factory
    def count_constraint(self, *args, **kwargs):
        return FuzzyLogic.CountConstraint(*args, **kwargs)
    
    @logic_factory
    def true_false(self, *args, **kwargs):
        return FuzzyLogic.TrueFalse(*args, **kwargs)

# this is a little hack to make nested classes pickleable
Constraint = FuzzyLogic.Constraint
Formula = FuzzyLogic.Formula
ComplexFormula = FuzzyLogic.ComplexFormula
Conjunction = FuzzyLogic.Conjunction
Disjunction = FuzzyLogic.Disjunction
Lit = FuzzyLogic.Lit
GroundLit = FuzzyLogic.GroundLit
GroundAtom = FuzzyLogic.GroundAtom
Equality = FuzzyLogic.Equality
Implication = FuzzyLogic.Implication
Biimplication = FuzzyLogic.Biimplication
Negation = FuzzyLogic.Negation
Exist = FuzzyLogic.Exist
TrueFalse = FuzzyLogic.TrueFalse
NonLogicalConstraint = FuzzyLogic.NonLogicalConstraint
CountConstraint = FuzzyLogic.CountConstraint
GroundCountConstraint = FuzzyLogic.GroundCountConstraint

    