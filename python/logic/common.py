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

from grammar import StandardGrammar, PRACGrammar
import re
from utils import unifyDicts, dict_union

# ======================================================================================
# decorator for storing the factory object in each created instance
# ======================================================================================
def logic_factory(method):
    def wrapper(self, *args, **kwargs):
        el = method(self,*args,**kwargs)
        el.logic = self
        return el
    return wrapper


PRED_ATOM = 1
PRED_FUNCTIONAL = 2
PRED_SOFTFUNC = 3


class Predicate(object):
    '''
    Represents a logical predicate and its properties.
    Fields:
    - predname:        the predicate name
    - argdoms:         the domain names of the arguments
    - mutex:           a boolean vector (same length as params) specifying
                       which argument is to be treated as functional.
    
    - predtype:        type of the predicate. May be one of the following:
                       - PRED_ATOM:        normal (binary) predicate
                       - PRED_FUNCTIONAL:  hard functional constraint (i.e. exactly one atom must be true)
                       - PRED_SOFTFUNC:    soft functional constraint (i.e. maximally one atom must be true)
    '''
    
    
    def __init__(self, predname, argdoms, mutex=None, softmutex=False):
        assert not softmutex or mutex is not None
        self.argdoms = argdoms
        self.predname = predname
        if mutex is None:
            self.mutex = [False] * len(argdoms)
        else:
            self.mutex = mutex
        if mutex is not None and any(mutex):
            if softmutex:
                self.predtype = PRED_SOFTFUNC
            else:
                self.predtype = PRED_FUNCTIONAL
        else:
            self.predtype = PRED_ATOM
            
            
    def getblockname(self, gndatom):
        '''
        Takes an instance of a ground atom and generates the name
        of the corresponding atomic block.
        '''
        nonfuncargs = [p if m is False else '_' for (m, p) in zip(self.mutex, gndatom.params)]
        return '%s(%s)' % (gndatom.predName, ','.join(nonfuncargs))
    
    
    def create_gndblock(self, blockname):
        '''
        Creates a new instance of an atomic ground block instance
        depending on the type of the predicate
        '''
        if self.predtype == PRED_FUNCTIONAL:
            return MutexBlock(blockname)
        elif self.predtype == PRED_SOFTFUNC:
            return SoftMutexBlock(blockname)
        elif self.predtype == PRED_ATOM:
            return AtomicBlock(blockname)
        else:
            raise Exception('Unkown predicate type.')


class AtomicBlock(object):
    '''
    Represents a (mutually exclusive) block of ground atoms.
    '''
    
    def __init__(self, blockname, *gndatoms):
        self.gndatoms = list(gndatoms)
        self.name = blockname
    
    
    def iteratoms(self):
        '''
        Yields all ground atoms in this block, sorted by atom index ascending
        '''
        for atom in sorted(self.gndatoms, key=lambda a: a.idx):
            yield atom
    
    
    def getNumberOfPossibleWorlds(self):
        raise Exception('%s does not implement getNumberOfPossibleWorlds()' % self.__class__.__name__)
    
    
    def generatePossibleWorldTuples(self, evidence=None):
        '''
        evidence mapping gnd atom indices to truth values
        '''
        raise Exception('%s does not implement generatePossibleWorldTuples()' % self.__class__.__name__)
    
    
    def __str__(self):
        return '%s: %s' % (self.name, ','.join(map(str, self.gndatoms)))


class BinaryBlock(AtomicBlock):
    '''
    Represents a binary ("normal") ground atom with the two states 1 and 0
    '''

    def getNumberOfPossibleWorlds(self):
        return 2


    def generatePossibleWorldTuples(self, evidence=None):
        '''
        Yields possible world values of this atom block.
        '''
        gndatom = self.gndatoms[0]
        if gndatom.idx in evidence:
            yield evidence[gndatom.idx]
            return
        for t in (0, 1):
            yield (t,)


class MutexBlock(AtomicBlock):
    '''
    Represents a mutually exclusive block of ground atoms.
    '''
    
    def getNumberOfPossibleWorlds(self):
        return len(self.gndatoms)
    
    
    def generatePossibleWorldTuples(self, evidence=None):
        if evidence is None:
            evidence = []
        for world in self._generatePossibleWorldTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generatePossibleWorldTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple([tuple(map(lambda x: 1 if x == 1 else 0, valpattern))])
            return
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)


class SoftMutexBlock(AtomicBlock):
    '''
    Represents a soft mutex block of ground atoms.
    '''
    
    def getNumberOfPossibleWorlds(self):
        return len(self.gndatoms) + 1


    def generatePossibleWorldTuples(self, evidence=None):
        if evidence is None:
            evidence = []
        for world in self._generatePossibleWorldTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generatePossibleWorldTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple([tuple(map(lambda x: 1 if x == 1 else 0, valpattern))])
            return
        yield tuple([0] * len(atomindices))
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)
                            
                            
class Logic(object):
    '''
    Abstract factory class for instantiating logical constructs like conjunctions, 
    disjunctions etc. Every specifc logic should implement the methods and return
    an instance of the respective element. They also might override the respective
    implementations and behavior of the logic.
    '''
    
    def __init__(self, grammar):
        '''
        - grammar:     an instance of grammar.Grammar
        '''
        self.grammar = eval(grammar)(self)
    
    def __getstate__(self):
        d = self.__dict__.copy()
        d['grammar'] = type(self.grammar).__name__
        return d
        
    def __setstate__(self, d):
        self.__dict__ = d
        self.grammar = eval(d['grammar'])(self)
        
    
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
    
    def parseFormula(self, formula):
        '''
        Returns the Formula object parsed by the grammar.
        '''
        return self.grammar.parseFormula(formula)
    
    def parsePredDecl(self, string):
        return self.grammar.parsePredDecl(string)
    
    def parseAtom(self, string):
        return self.grammar.parseAtom(string)    
    
    def parseDomDecl(self, decl):
        return self.grammar.parseDomDecl(decl)
    
    def parseLiteral(self, lit):
        return self.grammar.parseLiteral(lit)
    
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
    
    def isEquality(self, f):
        '''
        Determines wheter or not a formula is an equality consttaint.
        '''
        return isinstance(f, Logic.Equality)
    
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
                not isinstance(child, Logic.Equality) and \
                not isinstance(child, Logic.TrueFalse):
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
                not isinstance(child, Logic.Equality) and \
                not isinstance(child, Logic.TrueFalse):
                return False
        return True
    
    
    @staticmethod
    def iterEqVariableAssignments(eq, f, mln):
        fVars = f.getVariables(mln)
        eqVars_ = eq.getVariables(mln)
        if not set(eqVars_).issubset(fVars):
            raise Exception('Variable in (in)equality constraint not bound to a domain: %s' % eq)
        eqVars = {}
        for v in eqVars_:
            eqVars[v] = fVars[v]
        for assignment in Logic._iterEqVariableAssignments(mln, eqVars, {}):
            yield assignment
        
    
    @staticmethod
    def _iterEqVariableAssignments(mrf, variables, assignment):
        if len(variables) == 0:
            yield assignment
            return
        variables = dict(variables)
        variable, domName = variables.popitem()
        domain = mrf.domains[domName]
        for value in domain:
            for assignment in Logic._iterEqVariableAssignments(mrf, variables, dict_union(assignment, {variable: value})):
                yield assignment
        
    
# this is a little hack to make nested classes pickleable
Constraint = Logic.Constraint
Formula = Logic.Formula
ComplexFormula = Logic.ComplexFormula
Conjunction = Logic.Conjunction
Disjunction = Logic.Disjunction
Lit = Logic.Lit
GroundLit = Logic.GroundLit
GroundAtom = Logic.GroundAtom
Equality = Logic.Equality
Implication = Logic.Implication
Biimplication = Logic.Biimplication
Negation = Logic.Negation
Exist = Logic.Exist
TrueFalse = Logic.TrueFalse
NonLogicalConstraint = Logic.NonLogicalConstraint
CountConstraint = Logic.CountConstraint
GroundCountConstraint = Logic.GroundCountConstraint
