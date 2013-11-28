# -*- coding: utf-8 -*-
# FIRST-ORDER LOGIC -- PARSING AND GRAMMAR
#  
# (C) 2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
# (C) 2007-2012 by Dominik Jain
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

from pyparsing import *


class TreeBuilder(object):
    '''
    The parsing tree.
    '''
    
    def __init__(self, logic):
        self.logic = logic
        self.reset()
    
    def trigger(self, a, loc, toks, op):
        if op == 'lit':
            negated = False
            if toks[0] == '!' or toks[0] == '*':
                if toks[0] == '*':
                    negated = 2
                else:
                    negated = True
                toks = toks[1]
            else:
                toks = toks[0]
            self.stack.append(self.logic.lit(negated, toks[0], toks[1]))
        elif op == '!':
            if len(toks) == 1:
                formula = self.logic.negation(self.stack[-1:])
                self.stack = self.stack[:-1]
                self.stack.append(formula)
        elif op == 'v':
            if len(toks) > 1:
                formula = self.logic.disjunction(self.stack[-len(toks):])
                self.stack = self.stack[:-len(toks)]
                self.stack.append(formula)
        elif op == '^':
            if len(toks) > 1:
                formula = self.logic.conjunction(self.stack[-len(toks):])
                self.stack = self.stack[:-len(toks)]
                self.stack.append(formula)
        elif op == 'ex':
            if len(toks) == 2:
                formula = self.stack.pop()
                self.stack.append(self.logic.exist(toks[0], formula))
        elif op == '=>':
            if len(toks) == 2:
                children = self.stack[-2:]
                self.stack = self.stack[:-2]
                self.stack.append(self.logic.implication(children))
        elif op == '<=>':
            if len(toks) == 2:
                children = self.stack[-2:]
                self.stack = self.stack[:-2]
                self.stack.append(self.logic.biimplication(children))
        elif op == '=':
            if len(toks) == 2:
                self.stack.append(self.logic.equality(list(toks)))
        elif op == '!=':
            if len(toks) == 2:
                self.stack.append(self.logic.equality(list(toks), negated=True))
        elif op == 'count':
            print toks
            if len(toks) in (3,4):                
                pred, pred_params = toks[0]
                if len(toks) == 3:
                    fixed_params, op, count = [], toks[1], int(toks[2])
                else:
                    fixed_params, op, count = list(toks[1]), toks[2], int(toks[3])
                self.stack.append(self.logic.count_constraint(pred, pred_params, fixed_params, op, count))
        
    def reset(self):
        self.stack = []
                
    def getConstraint(self):
        if len(self.stack) > 1:
            raise Exception("Not a valid formula - reduces to more than one element %s" % str(self.stack))
        if len(self.stack) == 0:
            raise Exception("Constraint could not be parsed")
#         if not isinstance(self.stack[0], Logic.Constraint):
#             raise Exception("Not an instance of Constraint!")
        return self.stack[0]


# ======================================================================================
# Grammar implementations
# ======================================================================================

class Grammar(object):
    '''
    Abstract super class for all logic grammars.
    '''
    
    
    def __deepcopy__(self, memo):
        return self
    
    def parseFormula(self, s):
        self.tree.reset()
        self.formula.parseString(s)
        constr = self.tree.getConstraint()
        return constr
    
    def parsePredDecl(self, s):
        return self.predDecl.parseString(s)[0]
    
    def isVar(self, identifier):
        raise Exception('%s does not implement isVar().' % str(type(self)))
    
    def isConstant(self, identifier):
        return not self.isVar(identifier)
    
    
class StandardGrammar(Grammar):
    '''
    The standard MLN logic syntax.
    '''
    
    def __init__(self, logic):
        identifierCharacter = alphanums + '_' + '-' + "'"
        lcCharacter = alphas.lower()
        ucCharacter = alphas.upper()
        lcName = Word(lcCharacter, alphanums + '_')
        
        openRB = Literal("(").suppress()
        closeRB = Literal(")").suppress()
        
        domName = lcName
        
        constant = Word(ucCharacter, identifierCharacter) | Word(nums)
        variable = Word(lcCharacter, identifierCharacter)
        
        atomArgs = Group(delimitedList(constant | Combine(Optional("+") + variable)))
        predDeclArgs = Group(delimitedList(domName))
        
        predName = Word(identifierCharacter)
        
        atom = Group(predName + openRB + atomArgs + closeRB)
        literal = Optional(Literal("!") | Literal("*")) + atom
        
        predDecl = Group(predName + openRB + predDeclArgs + closeRB) + StringEnd()
        
        varList = Group(delimitedList(variable))
        count_constraint = Literal("count(").suppress() + atom + Optional(Literal("|").suppress() + varList) + Literal(")").suppress() + (Literal("=") | Literal(">=") | Literal("<=")) + Word(nums)
        
        formula = Forward()
        exist = Literal("EXIST ").suppress() + Group(delimitedList(variable)) + openRB + Group(formula) + closeRB
        equality = (constant|variable) + Literal("=").suppress() + (constant|variable)
        negation = Literal("!").suppress() + openRB + Group(formula) + closeRB
        item = literal | exist | equality | openRB + formula + closeRB | negation
        disjunction = Group(item) + ZeroOrMore(Literal("v").suppress() + Group(item))
        conjunction = Group(disjunction) + ZeroOrMore(Literal("^").suppress() + Group(disjunction))
        implication = Group(conjunction) + Optional(Literal("=>").suppress() + Group(conjunction))
        biimplication = Group(implication) + Optional(Literal("<=>").suppress() + Group(implication))
        constraint = biimplication | count_constraint
        formula << constraint
    
        tree = TreeBuilder(logic)
        literal.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'lit'))
        negation.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'!'))
        #item.setParseAction(lambda a,b,c: foo(a,b,c,'item'))
        disjunction.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'v'))
        conjunction.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'^'))
        exist.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"ex"))
        implication.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"=>"))
        biimplication.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"<=>"))
        equality.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"="))
        count_constraint.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'count'))
        
        self.tree = tree
        self.formula = formula + StringEnd()
        self.predDecl = predDecl
        
    def isVar(self, identifier):
        return identifier[0].islower() or identifier[0] == '+'
            

class PRACGrammar(Grammar):
    '''
    The specialized PRAC MLN grammar supporting infix not-equals and
    arbitrary constants. Variables need to start with '?'
    '''
    
    def __init__(self, logic):
        # grammar
        
        identifierCharacter = alphanums + 'ÄÖÜäöü' + '_' + '-' + "'" + '.' + ':' + ';' + '$'
        lcCharacter = alphas.lower()
        ucCharacter = alphas.upper()
        lcName = Word(lcCharacter, alphanums + '_')
        qMark = '?'
        
        openRB = Literal('(').suppress()
        closeRB = Literal(')').suppress()
        openSB = Literal('[').suppress()
        closeSB = Literal(']').suppress()
        
        domName = lcName
        
        constant = Word(identifierCharacter) | Word(nums)
        variable = Word(qMark, identifierCharacter)
        
        atomArgs = Group(delimitedList(constant | Combine(Optional("+") + variable)))
        predDeclArgs = Group(delimitedList(domName))
        
        predName = Word(identifierCharacter)
        
        atom = Group(predName + openRB + atomArgs + closeRB)
        literal = Optional(Literal("!") | Literal("*")) + atom
        
        predDecl = Group(predName + openRB + predDeclArgs + closeRB) + StringEnd()
        
        varList = Group(delimitedList(variable))
        count_constraint = Literal("count(").suppress() + atom + Optional(Literal("|").suppress() + varList) + Literal(")").suppress() + (Literal("=") | Literal(">=") | Literal("<=")) + Word(nums)
        
        formula = Forward()
        exist = Literal("EXIST ").suppress() + Group(delimitedList(variable)) + openRB + Group(formula) + closeRB
        equality = (constant|variable) + Literal("=").suppress() + (constant|variable)
        inequality = (constant|variable) + Literal('=/=').suppress() + (constant|variable)
        negation = Literal("!").suppress() + openRB + Group(formula) + closeRB
        item = literal | exist | equality | inequality | openRB + formula + closeRB | negation
        disjunction = Group(item) + ZeroOrMore(Literal("v").suppress() + Group(item))
        conjunction = Group(disjunction) + ZeroOrMore(Literal("^").suppress() + Group(disjunction))
        implication = Group(conjunction) + Optional(Literal("=>").suppress() + Group(conjunction))
        biimplication = Group(implication) + Optional(Literal("<=>").suppress() + Group(implication))
        constraint = biimplication | count_constraint
        formula << constraint

        tree = TreeBuilder(logic)
        literal.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'lit'))
        negation.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'!'))
        #item.setParseAction(lambda a,b,c: foo(a,b,c,'item'))
        disjunction.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'v'))
        conjunction.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'^'))
        exist.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"ex"))
        implication.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"=>"))
        biimplication.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"<=>"))
        equality.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"="))
        inequality.setParseAction(lambda a,b,c: tree.trigger(a,b,c,"!="))
        count_constraint.setParseAction(lambda a,b,c: tree.trigger(a,b,c,'count'))
        
        self.tree = tree
        self.formula = formula + StringEnd()
        self.predDecl = predDecl
        
    def isVar(self, identifier):
        '''
        Variables must start with a question mark (or the + operator, 
        anything else is considered a constant.
        '''
        return identifier[0] == '?' or identifier[0] == "+"


# main app for testing purposes only
if __name__=='__main__':
    from fol import FirstOrderLogic
    from fuzzy import FuzzyLogic
    
    test = 'parsing'
#     logic = FirstOrderLogic('PRACGrammar')
    logic = FuzzyLogic('PRACGrammar')
    
    if test == 'parsing':
        tests = [#"numberEats(o,2) <=> EXIST p, p2 (eats(o,p) ^ eats(o,p2) ^ !(o=p) ^ !(o=p2) ^ !(p=p2) ^ !(EXIST q (eats(o,q) ^ !(p=q) ^ !(p2=q))))",
                 #"EXIST y (rel(x,y) ^ EXIST y2 (!(y2=y) ^ rel(x,y2)) ^ !(EXIST y3 (!(y3=y) ^ !(y3=y2) ^ rel(x,y3))))",
                 "((a(?x) ^ b(?x)) v (c(?x) ^ !(d(?x) ^ e(?x) ^ g(?x)))) => f(?x)"
                 ]#,"foo(x) <=> !(EXIST p (foo(p)))", "numberEats(o,1) <=> !(EXIST p (eats(o,p) ^ !(o=p)))", "!a(c,d) => c=d", "c(b) v !(a(b) ^ b(c))"]
#         tests = ["((!a(x) => b(x)) ^ (b(x) => a(x))) v !(b(x)=>c(x))"]
#         tests = ["(EXIST y1 (rel(x,y1) ^ EXIST y2 (rel(x,y2) ^ !(y1=y2) ^ !(EXIST y3 (rel(?x,y3) ^ !(y1=y3) ^ !(y2=y3))))))"]
#         tests = ["EXIST ?x (a(?x))"]
#         tests = ['!foo(?x, ?y) ^ ?x =/= ?y']
        for test in tests:
            print "trying to parse %s..." % test
            f = logic.grammar.parseFormula(test).toCNF()
            print "got this: %s" % str(f)
            f.printStructure()
    elif test == 'NF':
        f = "a(x) <=> b(x)"
        f = "((a(x) ^ b(x)) v (c(x) ^ !(d(x) ^ e(x) ^ g(x)))) => f(x)"
        f = "(a(x) v (b(x) ^ c(x))) => f(x)"
        f = "(a(x) ^ b(x)) <=> (c(x) ^ d(x))"
        #f = "(a(x) ^ b(x)) v (c(x) ^ d(x))"        
        #f = "(a(x) ^ b(x)) v (c(x) ^ d(x)) v (e(x) ^ f(x))"
        #f = "(a(x) ^ b(x)) v (c(x) ^ d(x)) v (e(x) ^ f(x)) v (g(x) ^ h(x))"
        #f = "(a(x) ^ b(x) ^ e(x)) v (c(x) ^ d(x) ^ f(x))"
        #f = "(a(x) ^ b(x) ^ g(x)) v (c(x) ^ d(x) ^ h(x)) v (e(x) ^ f(x) ^ i(x))"
        #f = "(a(x) ^ !b(x) ^ !c(x)) v (!a(x) ^ b(x) ^ !c(x)) v (!a(x) ^ !b(x) ^ c(x))"
        #f = "(a(x) ^ b(x) ^ !c(x)) v (a(x) ^ !b(x) ^ c(x)) v (!a(x) ^ b(x) ^ c(x))"
        #f = "(a(x) ^ !b(x)) v (!a(x) ^ b(x))"
        #f = "(a(x) ^ b(x) ^ !c(x)) v (a(x) ^ !b(x) ^ c(x)) v (!a(x) ^ b(x) ^ c(x))"
        #f = "(a(x) ^ b(x) ^ !c(x) ^ !d(x)) v (a(x) ^ !b(x) ^ c(x) ^ !d(x)) v (!a(x) ^ b(x) ^ c(x) ^ !d(x)) v (a(x) ^ !b(x) ^ !c(x) ^ d(x)) v (!a(x) ^ b(x) ^ !c(x) ^ d(x)) v (!a(x) ^ !b(x) ^ c(x) ^ d(x))"
        #f = "consumesAny(P,Coffee) <=> ((consumedBy(C3,P) ^ goodsT(C3,Coffee)) v (consumedBy(C2,P) ^ goodsT(C2,Coffee)) v (consumedBy(C1,P) ^ goodsT(C1,Coffee)) v (consumedBy(C4,P) ^ goodsT(C4,Coffee)))"
        #f = "consumesAny(P,Coffee) <=> ((consumedBy(C3,P) ^ goodsT(C3,Coffee)) v (consumedBy(C2,P) ^ goodsT(C2,Coffee)) v (consumedBy(C1,P) ^ goodsT(C1,Coffee)))"
        f = g.parseFormula(f)
        f = f.toCNF()
        f.printStructure()
    elif test == 'count':
        c = "count(directs(a,m)|m) >= 4"
        c = "count(foo(a,Const)) = 2"
        #c = count_constraint.parseString(c)
        c = logic.grammar.parseFormula(c).toCNF()
        print str(c)
        pass
    
    
