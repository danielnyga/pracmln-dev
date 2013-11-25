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

import fol
from logic.fol import isVar
import logging


def min_undef(*args):
    '''
    Custom minimum function return None if one of its arguments
    is None and min(*args) otherwise.
    '''
    return reduce(lambda x, y: None if (x is None or y is None) else min(x, y), *args)

def max_undef(*args):
    '''
    Custom maximum function return None if one of its arguments
    is None and max(*args) otherwise.
    '''
    return reduce(lambda x, y: None if x is None or y is None else max(x, y), *args)


class Formula(fol.Formula):
    '''
    Represents a formula in fuzzy logic.
    '''
    pass


class ComplexFormula(fol.ComplexFormula):
    pass


class Lit(fol.Lit):
    
    def simplify(self, mrf):
        if any(map(isVar, self.params)):
            return Lit(self.negated, self.predName, self.params)
        s = "%s(%s)" % (self.predName, ",".join(self.params))
        truth = mrf.gndAtoms[s].isTrue(mrf.evidence) 
        if truth is None:
            return self
        else:
            if self.negated: truth = 1 - truth
            return TrueFalse(truth)


class GroundLit(fol.GroundLit):
    
    def isTrue(self, world_values):
        truth = self.gndAtom.isTrue(world_values)
        if truth is None: return None
        return (1 - truth) if self.negated else truth 

    def simplify(self, mrf):
        f = self.gndAtom.simplify(mrf)
        if isinstance(f, TrueFalse):
            if self.negated:
                return f.invert()
            else:
                return f
        return GroundLit(self.gndAtom, self.negated)
    
    
class GroundAtom(fol.GroundAtom):
    
    def isTrue(self, world_values):
        val = world_values[self.gndAtom.idx]
        if val is None: return None
        return val
    
    def simplify(self, mrf):
        truth = mrf.evidence[self.idx]
        if truth is None:
            return self
        return TrueFalse(truth)


class Negation(fol.Negation):
    
    def isTrue(self, world_values):
        return 1 - self.children[0].isTrue(world_values)
    
    def simplify(self, mrf):
        f = self.children[0].simplify(mrf)
        if isinstance(f, TrueFalse):
            return f.invert()
        else:
            return Negation([f])

class Conjunction(fol.Conjunction):
    
    def isTrue(self, world_values):
        return min_undef(map(lambda a: a.isTrue(world_values), self.children))
    
    def simplify(self, mrf):
        sf_children = []
        minTruth = None
        for child in self.children:
            child = child.simplify(mrf)
            if isinstance(child, TrueFalse):
                if minTruth is None or child.isTrue() < minTruth:
                    minTruth = child.isTrue()
            else:
                sf_children.append(child)
        if len(sf_children) == 1 and minTruth is None:
            return sf_children[0]
        elif len(sf_children) >= 1 and (minTruth is None or minTruth > 0):
            if minTruth is not None:
                sf_children.append(TrueFalse(minTruth))
            return Conjunction(sf_children)
        else:
            return TrueFalse(minTruth)


class Disjunction(fol.Disjunction):
    
    def isTrue(self, world_values):
        return max_undef(map(lambda a: a.isTrue(world_values), self.children))

    def simplify(self, mrf):
        sf_children = []
        maxTruth = None
        for child in self.children:
            child = child.simplify(mrf)
            if isinstance(child, TrueFalse):
                if maxTruth is None and child.isTrue() > maxTruth:
                    maxTruth = child.isTrue()
            else:
                sf_children.append(child)
        if len(sf_children) == 1 and maxTruth is None:
            return sf_children[0]
        elif len(sf_children) >= 1 and (maxTruth is None or maxTruth < 1):
            if maxTruth is not None:
                sf_children.append(TrueFalse(maxTruth))
            return Disjunction(sf_children)
        else:
            return TrueFalse(maxTruth)
        

class Implication(fol.Implication):
    
    def isTrue(self, world_values):
        return max_undef(1. - self.children[0].isTrue(world_values), self.children[1].isTrue(world_values))

    def simplify(self, mrf):
        return Disjunction([Negation([self.children[0]]), self.children[1]]).simplify(mrf)
    
    
class Biimplication(fol.Biimplication):
    
    def isTrue(self, world_values):
        return min_undef(self.children[0].isTrue(world_values), self.children[1].isTrue(world_values))

    def simplify(self, mrf):
        c1 = Disjunction([Negation([self.children[0]]), self.children[1]])
        c2 = Disjunction([self.children[0], Negation([self.children[1]])])
        return Conjunction([c1,c2]).simplify(mrf)
    
    
class Equality(fol.Equality):
    
    def isTrue(self, world_values):
        if any(map(isVar, self.params)):
            return None
        equals = 1 if (self.params[0] == self.params[1]) else 0
        return (1 - equals) if self.negated else equals
    
    def simplify(self, mrf):
        truth = self.isTrue(mrf.evidence) 
        if truth != None: return TrueFalse(truth)
        return Equality(list(self.params), negated=self.negated)
    
class TrueFalse(Formula):
    
    def invert(self):
        return TrueFalse(1 - self.value)


class Exist(fol.Exist):
    pass


if __name__ == '__main__':
    
    print min_undef(0, 1, 0)

    