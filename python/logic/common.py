# LOGIC -- COMMON BASE CLASSES
#
# (C) 2012-2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
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


# ======================================================================================
# decorator for storing the factory object in each created instance
# ======================================================================================
def logic_factory(method):
    def wrapper(self, *args, **kwargs):
        el = method(self,*args,**kwargs)
        el.logic = self
        return el
    return wrapper


class Logic(object):
    '''
    Abstract factory class for instantiating logical constructs like conjunctions, 
    disjunctions etc. Every specifc logic should implement the methods and return
    an instance of the respective element. They also might override the respective
    implementations of behaviors of the logic.
    '''
    
    def __init__(self, grammar):
        '''
        - grammar:     an instance of grammar.Grammar
        '''
        self.grammar = grammar
    
    
    # ======================================================================================
    # abstract super classes of all logical (and non-logical) constraints
    # ======================================================================================
    # TODO: Move the basic functionality of logics from fol to here
    class Constraint(object): pass
    class Formula(Constraint): pass
    class ComplexFormula(Formula): pass
    class Conjunction(ComplexFormula): pass
    class Disjunction(ComplexFormula): pass
    class Lit(Formula): pass
    class GroundLit(Formula): pass
    class GroundAtom(Formula): pass
    class Equality(ComplexFormula): pass
    class Implication(ComplexFormula): pass
    class Biimplication(ComplexFormula): pass
    class Negation(ComplexFormula): pass
    class Exist(ComplexFormula): pass
    class TrueFalse(Formula): pass
    class NonLogicalConstraint(Constraint): pass
    class CountConstraint(NonLogicalConstraint): pass
    class GroundCountConstraint(NonLogicalConstraint): pass
    
    
    def isVar(self, identifier):
        '''
        Returns True if identifier is a logical variable according
        to the used grammar, and False otherwise.
        '''
        return self.grammar.isVar(identifier)
    
    def isConstant(self, identifier):
        '''
        Returns True if identifier is a logical constant according
        to the used grammar, and False otherwise.
        '''
        return self.grammar.isConstant(identifier)
    
    @logic_factory
    def conjunction(self, *args, **kwargs):
        '''
        Returns a new instance of a Conjunction object.
        '''
        raise Exception('%s does not implement conjunction()' % str(type(self)))
    
    @logic_factory
    def disjunction(self, *args, **kwargs):
        '''
        Returns a new instance of a Disjunction object.
        '''
        raise Exception('%s does not implement disjunction()' % str(type(self)))
    
    @logic_factory    
    def negation(self, *args, **kwargs):
        '''
        Returns a new instance of a Negation object.
        '''
        raise Exception('%s does not implement negation()' % str(type(self)))
    
    @logic_factory
    def implication(self, *args, **kwargs):
        '''
        Returns a new instance of a Implication object.
        '''
        raise Exception('%s does not implement implication()' % str(type(self)))
    
    @logic_factory
    def biimplication(self, *args, **kwargs):
        '''
        Returns a new instance of a Biimplication object.
        '''
        raise Exception('%s does not implement biimplication()' % str(type(self)))
    
    @logic_factory
    def equality(self, *args, **kwargs):
        '''
        Returns a new instance of a Equality object.
        '''
        raise Exception('%s does not implement equality()' % str(type(self)))
    
    @logic_factory
    def exist(self, *args, **kwargs):
        '''
        Returns a new instance of a Exist object.
        '''
        raise Exception('%s does not implement exist()' % str(type(self)))
    
    @logic_factory
    def gnd_atom(self, *args, **kwargs):
        '''
        Returns a new instance of a GndAtom object.
        '''
        raise Exception('%s does not implement gnd_atom()' % str(type(self)))
    
    @logic_factory
    def lit(self, *args, **kwargs):
        '''
        Returns a new instance of a Lit object.
        '''
        raise Exception('%s does not implement lit()' % str(type(self)))
    
    @logic_factory
    def gnd_lit(self, *args, **kwargs):
        '''
        Returns a new instance of a GndLit object.
        '''
        raise Exception('%s does not implement gnd_lit()' % str(type(self)))
    
    @logic_factory
    def count_constraint(self, *args, **kwargs):
        '''
        Returns a new instance of a CountConstraint object.
        '''
        raise Exception('%s does not implement count_constraint()' % str(type(self)))
    
    @logic_factory
    def true_false(self, *args, **kwargs):
        '''
        Returns a new instance of a TrueFalse constant object.
        '''
        raise Exception('%s does not implement true_false()' % str(type(self)))
    
    @logic_factory
    def create(self, clazz, *args, **kwargs):
        '''
        Takes the type of a logical element (class type) and creates
        a new instance of it.
        '''
        return clazz(*args, **kwargs)
    

    def isLiteral(self, f):
        '''
        Determines whether or not a formula is a literal.
        '''
        return isinstance(f, Logic.GroundLit) or isinstance(f, Logic.Lit) or isinstance(f, Logic.GroundAtom)
    
    def isConjunctionOfLiterals(self, f):
        '''
        Returns true if the given formula is a conjunction of literals.
        '''
        if self.isLiteral(f): return True
        if not isinstance(f, Logic.Conjunction):
            return False
        for child in f.children:
            if not isinstance(child, Logic.Lit) and \
                not isinstance(child, Logic.GroundLit) and \
                not isinstance(child, Logic.GroundAtom) and \
                not isinstance(child, Logic.Equality):
                return False
        return True
    
    def isDisjunctionOfLiterals(self, f):
        '''
        Returns true if the given formula is a clause (a disjunction of literals)
        '''
        if self.isLiteral(f): return True
        if not isinstance(f, Logic.Disjunction):
            return False
        for child in f.children:
            if not isinstance(child, Logic.Lit) and \
                not isinstance(child, Logic.GroundLit) and \
                not isinstance(child, Logic.GroundAtom) and \
                not isinstance(child, Logic.Equality):
                return False
        return True
