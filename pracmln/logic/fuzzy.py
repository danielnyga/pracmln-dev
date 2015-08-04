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

from common import Logic

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
        return reduce(lambda x, y: None if (x is None or y is None) else min(x, y), args)
    
    
    @staticmethod
    def max_undef(*args):
        '''
        Custom maximum function return None if one of its arguments
        is None and max(*args) otherwise.
        '''
        if len(filter(lambda x: x == 1, args)) > 0:
            return 1
        return reduce(lambda x, y: None if x is None or y is None else max(x, y), args)
    
    
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
    
    
    class Constraint(Logic.Constraint): pass
    
    
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class Formula(Logic.Formula): pass
    
    
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class ComplexFormula(Logic.Formula): pass


#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
    
    
    class Lit(Logic.Lit): pass
    
    
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
    
    
    class GroundLit(Logic.GroundLit): pass
        

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class GroundAtom(Logic.GroundAtom):
        
        def truth(self, world):
            return world[self.idx]
        

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #

    
    class Negation(Logic.Negation, ComplexFormula):
        
        def truth(self, world):
            val = self.children[0].truth(world)
            return None if val is None else 1. - val
        
        
        def simplify(self, mrf):
            f = self.children[0].simplify(mrf)
            if isinstance(f, Logic.TrueFalse):
                return f.invert()
            else:
                return self.logic.negation([f])
    

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
    
    
    class Conjunction(Logic.Conjunction, ComplexFormula):
        
        
        def truth(self, world):
            truthChildren = map(lambda a: a.truth(world), self.children)
            return FuzzyLogic.min_undef(*truthChildren)
        
        
        def simplify(self, mrf):
            sf_children = []
            minTruth = None
            for child_ in self.children:
                child = child_.simplify(mrf)
                if isinstance(child, Logic.TrueFalse):
                    truth = child.truth()
                    if truth == 0:
                        return self.mln.logic.true_false(0.)
                    if minTruth is None or truth < minTruth:
                        minTruth = truth
                else:
                    sf_children.append(child)
            if minTruth is not None and minTruth < 1 or minTruth == 1 and len(sf_children) == 0:
                sf_children.append(self.mln.logic.true_false(minTruth))
            if len(sf_children) > 1:
                return self.mln.logic.conjunction(sf_children)
            elif len(sf_children) == 1:
                return sf_children[0]
            else:
                assert False # should be unreachable
    
    
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #

    
    class Disjunction(Logic.Disjunction, ComplexFormula):
        
        
        def truth(self, world):
            return FuzzyLogic.max_undef(*map(lambda a: a.truth(world), self.children))
    
    
        def simplify(self, mrf):
            sf_children = []
            maxTruth = None
            for child in self.children:
                child = child.simplify(mrf)
                if isinstance(child, Logic.TrueFalse):
                    truth = child.truth()
                    if truth == 1:
                        return self.mln.logic.true_false(1.)
                    if maxTruth is None or truth > maxTruth:
                        maxTruth = truth
                else:
                    sf_children.append(child)
            if maxTruth is not None and maxTruth > 0 or (maxTruth == 0 and len(sf_children) == 0):
                sf_children.append(self.mln.logic.true_false(maxTruth))
            if len(sf_children) > 1:
                return self.mln.logic.disjunction(sf_children)
            elif len(sf_children) == 1:
                return sf_children[0]
            else:
                assert False
            

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class Implication(Logic.Implication, ComplexFormula):
        
        def truth(self, world):
            ant = self.children[0].truth(world)
            return FuzzyLogic.max_undef(None if ant is None else 1. - ant, self.children[1].truth(world))
    
        def simplify(self, mrf):
            return self.mln.logic.disjunction([self.mln.logic.negation([self.children[0]]), self.children[1]]).simplify(mrf)
        
        
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class Biimplication(Logic.Biimplication, ComplexFormula):
        
        def truth(self, world):
            return FuzzyLogic.min_undef(self.children[0].truth(world), self.children[1].truth(world))
    
        def simplify(self, mrf):
            c1 = self.mln.logic.disjunction([self.mln.logic.negation([self.children[0]]), self.children[1]])
            c2 = self.mln.logic.disjunction([self.children[0], self.mln.logic.negation([self.children[1]])])
            return self.mln.logic.conjunction([c1,c2]).simplify(mrf)
        

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #

        
    class Equality(Logic.Equality):
        
        def truth(self, world=None):
            if any(map(self.logic.isvar, self.args)):
                return None
            equals = 1. if (self.args[0] == self.args[1]) else 0.
            return (1. - equals) if self.negated else equals
        
        def simplify(self, mrf):
            truth = self.truth(mrf.evidence) 
            if truth != None: return self.mln.logic.true_false(truth)
            return self.mln.logic.equality(list(self.args), negated=self.negated)


#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #

        
    class TrueFalse(Formula, Logic.TrueFalse):
        
        def __init__(self, value):
            if not (value >= 0. and value <= 1.):
                raise Exception('Illegal truth value: %s' % value)
            Logic.TrueFalse(self, value)
        
        def __str__(self):
            return str(self.value)
        
        def cstr(self, color=False):
            return str(self)
        
        def invert(self):
            return self.mln.logic.true_false(1. - self.value)
    

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    class Exist(Logic.Exist, Logic.ComplexFormula):
        pass


#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #


    def conjunction(self, *args, **kwargs):
        return FuzzyLogic.Conjunction(*args, **kwargs)
    
    
    def disjunction(self, *args, **kwargs):
        return FuzzyLogic.Disjunction(*args, **kwargs)
    
    
    def negation(self, *args, **kwargs):
        return FuzzyLogic.Negation(*args, **kwargs)
    
    
    def implication(self, *args, **kwargs):
        return FuzzyLogic.Implication(*args, **kwargs)
    
    
    def biimplication(self, *args, **kwargs):
        return FuzzyLogic.Biimplication(*args, **kwargs)
    
    
    def equality(self, *args, **kwargs):
        return FuzzyLogic.Equality(*args, **kwargs)
    
    
    def exist(self, *args, **kwargs):
        return FuzzyLogic.Exist(*args, **kwargs)

    
    def gnd_atom(self, *args, **kwargs):
        return FuzzyLogic.GroundAtom(*args, **kwargs)

    
    def lit(self, *args, **kwargs):
        return FuzzyLogic.Lit(*args, **kwargs)

    
    def gnd_lit(self, *args, **kwargs):
        return FuzzyLogic.GroundLit(*args, **kwargs)

    
    def count_constraint(self, *args, **kwargs):
        return FuzzyLogic.CountConstraint(*args, **kwargs)

    
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
