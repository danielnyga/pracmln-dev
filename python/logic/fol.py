# FIRST-ORDER LOGIC -- PROCESSING
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

import logging
import itertools
from common import Logic, logic_factory
from utils import colorize, predicate_color
from mln.errors import NoSuchDomainError


class FirstOrderLogic(Logic):
    '''
    Factory class for first-order logic.
    '''

    class Constraint(Logic.Constraint):
        '''
        Super class of every constraint.
        '''
        
        def getTemplateVariants(self):
            '''
            Gets all the template variants of the constraint for the given mln/ground markov random field.
            '''
            raise Exception("%s does not implement getTemplateVariants" % str(type(self)))
        
        def isTrue(self, world_values):
            '''
            Returns True if the constraint is satisfied given a complete possible world
                    world_values: a possible world as a list of truth values
            '''
            raise Exception("%s does not implement isTrue" % str(type(self)))
    
        def isLogical(self):
            '''
            Returns whether this is a logical constraint, i.e. a logical formula
            '''
            raise Exception("%s does not implement isLogical" % str(type(self)))
    
        def iterGroundings(self, mrf, simplify=False, domains=None):
            '''
            Iteratively yields the groundings of the formula for the given ground MRF
            - simplify:     If set to True, the grounded formulas will be simplified
                            according to the evidence set in the MRF.
            - domains:      If None, the default domains will be used for grounding.
                            If its a dict mapping the variable names to a list of values,
                            these values will be used instead.
            '''
            raise Exception("%s does not implement iterGroundings" % str(type(self)))
        
        def idxGroundAtoms(self, l = None):
            raise Exception("%s does not implement idxGroundAtoms" % str(type(self)))
        
        def getGroundAtoms(self, l = None):
            raise Exception("%s does not implement getGroundAtoms" % str(type(self)))
    
        
    class Formula(Logic.Formula, Constraint):
        ''' 
        The base class for all logical constraints.
        '''
        
        def containsGndAtom(self, idxGndAtom):
            if not hasattr(self, "children"):
                return False
            for child in self.children:
                if child.containsGndAtom(idxGndAtom):
                    return True
            return False
    
        def idxGroundAtoms(self, l = None):
            if l == None: l = []
            if not hasattr(self, "children"):
                return l
            for child in self.children:
                child.idxGroundAtoms(l)
            return l
    
        def getGroundAtoms(self, l = None):
            if l == None: l = []
            if not hasattr(self, "children"):
                return l
            for child in self.children:
                child.getGroundAtoms(l)
            return l
    
        def getTemplateVariants(self, mln):
            '''
            Gets all the template variants of the formula for the given
            MLN (ground Markov Random Field)
            '''
            log = logging.getLogger('fol')
            uniqueVars = mln.uniqueFormulaExpansions.get(self, [])
            if len(uniqueVars) > 0:
                uniqueVarsDomain = list(mln.domains[self.getVarDomain(uniqueVars[0], mln)])
            else:
                uniqueVarsDomain = None
            variables = []
            domains = []
            for v, d in self._getTemplateVariables(mln).iteritems():
                # temporarily remove the unique variable combinations
                if v in uniqueVars: continue
                variables.append(v)
                domains.append(list(mln.domains[d]))
            variants_tmp = []
            for variant in self._getTemplateVariants(mln, variables, domains):
                variants_tmp.extend(self._groundTemplate(variant))
            # add the variants with unique template variable constraints
            variants = []
            if len(uniqueVars) == 0:
                variants = variants_tmp
            else:
                for variant in variants_tmp:
                    for valueCombination in itertools.combinations_with_replacement(uniqueVarsDomain, len(uniqueVars)):
                        assignment = dict([(var, val) for var, val in zip(uniqueVars, valueCombination)])
                        variants.extend(variant._groundTemplate(assignment))
            return variants
    
        def _getTemplateVariants(self, mln, variables, domains):
            if len(variables) == 0:
                yield {}
                return
            # ground the next variable
            for value in domains[0]:
                for assignment in self._getTemplateVariants(mln, variables[1:], domains[1:]):
                    yield dict(assignment.items() + [(variables[0], value)])
                
        def _getTemplateVariables(self, mln, variable = None):
            '''
            Gets all variables of this formula that are required to be expanded 
            (i.e. variables to which a '+' was appended) and returns a 
            mapping (dict) from variable name to domain name.
            '''
            raise Exception("%s does not implement _getTemplateVariables" % str(type(self)))
        
        def _groundTemplate(self, assignment):
            '''
            Grounds this formula for the given assignment of template variables 
            and returns a list of formulas, the list of template variants
            - assignment: a mapping from variable names to constants
            '''
            raise Exception("%s does not implement _groundTemplate" % str(type(self)))
    
        def iterGroundings(self, mrf, simplify=False, domains=None):
            '''
            Iteratively yields the groundings of the formula for the given grounder
            - mrf:           an object, such as an MRF instance, which
                                 - has an "mln" member (MarkovLogicNetwork instance)
                                 - has a "domains" member (like an MLN/MRF)
                                 - has a "gndAtoms" member that can be indexed, i.e. gndAtoms[string] should 
                                   return a ground atom instance
            - simplify:     If set to True, the grounded formulas will be simplified
                            according to the evidence set in the MRF.
            - domains:      If None, the default domains will be used for grounding.
                            If its a dict mapping the variable names to a list of values,
                            these values will be used instead.
            '''
            try:
                variables = self.getVariables(mrf.mln)
            except Exception, e:
                raise Exception("Error grounding '%s': %s" % (str(self), str(e)))
            for grounding, referencedGndAtoms in self._iterGroundings(mrf, variables, {}, simplify, domains):
                yield grounding, referencedGndAtoms
            
        def iterTrueVariableAssignments(self, mrf, world, truthThreshold=1.0, strict=False, includeUnknown=False, partialAssignment=None):
            '''
            Iteratively yields the variable assignments (as a dict) for which this
            formula exceeds the given truth threshold. Same as iterGroundings, 
            but returns variable mappings for only assignments rendering this formula true.
            If includeUnknown is True, groundings with the truth value 'None' are returned
            as well.
            If strict is True, the truth value must be strictly greater than the threshold,
            if False, its greater or equal.
            '''
            if partialAssignment is None:
                partialAssignment = {}
            try:
                variables = self.getVariables(mrf.mln)
                for var in partialAssignment:
                    if var in variables: del variables[var]
            except Exception, e:
                raise Exception("Error grounding '%s': %s" % (str(self), str(e)))
            for assignment in self._iterTrueVariableAssignments(mrf, variables, partialAssignment, world, 
                                                                dict(variables), truthThreshold=truthThreshold, strict=strict, includeUnknown=includeUnknown):
                yield assignment
        
        def _iterTrueVariableAssignments(self, mrf, variables, assignment, world, allVariables, truthThreshold=1.0, strict=False, includeUnknown=False):
            # if all variables have been grounded...
            if variables == {}:
                referencedGndAtoms = []
                gndFormula = self.ground(mrf, assignment, referencedGndAtoms)
                truth = gndFormula.isTrue(world)
                if (((truth >= truthThreshold) if not strict else (truth > truthThreshold)) and truth is not None) or (truth is None and includeUnknown):
                    trueAssignment = {}
                    for v in allVariables:
                        trueAssignment[v] = assignment[v]
                    yield trueAssignment
                return
            # ground the first variable...
            varname, domName = variables.popitem()
            assignment_ = dict(assignment) # copy for avoiding side effects
            if domName not in mrf.domains: raise NoSuchDomainError('The domain %s does not exist, but is needed to ground the formula %s' % (domName, str(self)))
            for value in mrf.domains[domName]: # replacing it with one of the constants
                assignment_[varname] = value
                # recursive descent to ground further variables
                for ass in self._iterTrueVariableAssignments(mrf, dict(variables), assignment_, world, allVariables, 
                                                             truthThreshold=truthThreshold, strict=strict, includeUnknown=includeUnknown):
                    yield ass
                    
        def _iterGroundings(self, mrf, variables, assignment, simplify=False, domains=None):
            # if all variables have been grounded...
            if variables == {}:
                referencedGndAtoms = []
                gndFormula = self.ground(mrf, assignment, referencedGndAtoms, simplify, domains)
                yield gndFormula, referencedGndAtoms
                return
            # ground the first variable...
            varname, domName = variables.popitem()
            domain = domains[varname] if domains is not None else mrf.domains[domName]
            for value in domain: # replacing it with one of the constants
                assignment[varname] = value
                # recursive descent to ground further variables
                for g, r in self._iterGroundings(mrf, dict(variables), assignment, simplify, domains):
                    yield g, r
        
        def getVariables(self, mln, variables = None, constants=None):
            raise Exception("%s does not implement getVariables" % str(type(self)))
        
        def getPredicateNames(self, predNames=None):
            '''
            Returns a list of all predicate names used in this formula.
            '''
            raise Exception('%s does not implement getPredicateNames' % str(type(self)))
        
        def ground(self, mln, assignment, referencedAtoms = None, simplify=False, allowPartialGroundings=False):
            '''grounds the formula using the given assignment of variables to values/constants and, if given a list in referencedAtoms, fills that list with indices of ground atoms that the resulting ground formula uses
                    returns the ground formula object
                    assignment: mapping of variable names to values'''
            raise Exception("%s does not implement ground" % str(type(self)))
        
        def duplicate(self):
            return self.ground(None, {}, allowPartialGroundings=True)
        
        def getVarDomain(self, varname, mln):
            raise Exception("%s does not implement getVarDomain" % str(type(self)))
            
        def toCNF(self, level=0):
            '''
            Convert to conjunctive normal form.
            '''
            return self
        
        def toNNF(self, level=0):
            '''
            Convert to negation normal form.
            '''
            return self
            
        def printStructure(self, mrf=None, level=0):
            print "%*c" % (level * 4,' '),
            print "%s: %s = %s" % (str(type(self)), str(self), self.isTrue(mrf.evidence) if mrf is not None else None)
            if hasattr(self, 'children'):
                for child in self.children:
                    child.printStructure(mrf, level+1)
        
        def isLogical(self):
            return True
        
        def simplify(self, mrf):
            '''
            Simplify the formula by evaluating it with respect to the ground atoms given 
            by the evidence in the mrf.
            '''
            raise Exception('%s does not implement simplify' % str(type(self)))
        
        def iterLiterals(self):
            '''
            Traverses the formula and returns a generator for the literals it contains.
            ''' 
            if not hasattr(self, 'children'):
                yield self
                return
            else:
                for child in self.children:
                    for lit in child.iterLiterals():
                        yield lit
        
        def isTrue(self, world_values):
            '''
            Evaluates the formula for truth wrt. the truth values
            of ground atoms (world_values being a dict: gndAtomIdx -> {1, 0, None}
            '''
            raise Exception('%s does not implement isTrue' % str(type(self)))
        
        def computeNoOfGroundings(self, mrf):
            '''
            Computes the number of ground formulas based on the domains of free
            variables in this formula. (NB: this does _not_ generate the groundings.)
            '''
            gf_count = 1
            for _, dom in self.getVariables(mrf).iteritems():
                domain = mrf.domains[dom]
                gf_count *= len(domain)
            return gf_count
    
        def maxTruth(self, world_values):
            '''
            Returns the maximum truth value of this formula given the evidence.
            For FOL, this is always 1 if the formula is not rendered false by evidence.
            '''
            raise Exception('%s does not implement maxTruth()' % self.__class__.__name__)
        
        def minTruth(self, world_values):
            '''
            Returns the minimum truth value of this formula given the evidence.
            For FOL, this is always 0 if the formula is not rendered true by evidence.
            '''
            raise Exception('%s does not implement maxTruth()' % self.__class__.__name__)
        
    class ComplexFormula(Logic.ComplexFormula, Formula):
        '''
        A formula that has other formulas as subelements (children)
        '''
        
        def getVariables(self, mln, variables = None, constants = None):
            '''
            Get the free (unquantified) variables of the formula in a dict that maps the variable name to the corresp. domain name
            The vars and constants parameters can be omitted.
            If vars is given, it must be a dictionary with already known variables.
            If constants is given, then it must be a dictionary that is to be extended with all constants appearing in the formula;
                it will be a dictionary mapping domain names to lists of constants
            If constants is not given, then constants are not collected, only variables.
            The dictionary of variables is returned.
            '''
            if variables is None: variables = {}
            for child in self.children:
                if not hasattr(child, "getVariables"): continue
                variables = child.getVariables(mln, variables, constants)
            return variables
        
        def getConstants(self, mln, constants = None):
            ''' 
            Get the constants appearing in the formula in a dict that maps the constant 
            name to the domain name the constant belongs to.
            '''
            if constants == None: constants = {}
            for child in self.children:
                if not hasattr(child, "getConstants"): continue
                constants = child.getConstants(mln, constants)
            return constants  
    
        def ground(self, mrf, assignment, referencedGndAtoms = None, simplify=False, allowPartialGroundings=False):
            children = []
            for child in self.children:
                gndChild = child.ground(mrf, assignment, referencedGndAtoms, simplify, allowPartialGroundings)
                children.append(gndChild)
            gndFormula = self.logic.create(type(self), children)
            if simplify:
                gndFormula = gndFormula.simplify(mrf)
            return gndFormula
    
        def _groundTemplate(self, assignment):
            variants = [[]]
            for child in self.children:
                childVariants = child._groundTemplate(assignment)
                new_variants = []
                for variant in variants:
                    for childVariant in childVariants:
                        v = list(variant)
                        v.append(childVariant)
                        new_variants.append(v)
                variants = new_variants
            final_variants = []
            for variant in variants:
                if isinstance(self, Logic.Exist):
                    final_variants.append(self.logic.exist(self.vars, variant[0]))
                else:
                    final_variants.append(self.logic.create(type(self), variant))
                    
            return final_variants
    
        def getVarDomain(self, varname, mln):
            for child in self.children:
                dom = child.getVarDomain(varname, mln)
                if dom != None:
                    return dom
            return None
    
        def _getTemplateVariables(self, mln, variables = None):
            if variables == None: 
                variables = {}
            for child in self.children:
                if not hasattr(child, "_getTemplateVariables"): continue
                variables = child._getTemplateVariables(mln, variables)
            return variables
        
        def getPredicateNames(self, predNames=None):
            if predNames is None:
                predNames = []
            for child in self.children:
                if not hasattr(child, 'getPredicateNames'): continue
                predNames = child.getPredicateNames(predNames)
            return predNames
            
    class Lit(Logic.Lit, Formula):
        '''
        Represents a literal.
        '''
        
        def __init__(self, negated, predName, params):
            self.negated = negated
            self.predName = predName
            self.params = list(params)
    
        def __str__(self):
            return {True:"!", False:""}[self.negated] + self.predName + "(" + ", ".join(self.params) + ")"
    
        def cstr(self, color=False):
            return {True:"!", False:""}[self.negated] + colorize(self.predName, predicate_color, color) + "(" + ", ".join(self.params) + ")"
    
        def getVariables(self, mln, variables = None, constants = None):
            if variables == None: 
                variables = {}
            paramDomains = mln.predicates[self.predName]
            if len(paramDomains) != len(self.params): 
                raise Exception("Wrong number of parameters in '%s'; expected %d!" % (str(self), len(paramDomains)))
            for i,param in enumerate(self.params):
                if self.logic.isVar(param):
                    varname = param
                    domain = paramDomains[i]
                    if varname in variables and variables[varname] != domain:
                        raise Exception("Variable '%s' bound to more than one domain" % varname)
                    variables[varname] = domain
                elif constants is not None:
                    domain = paramDomains[i]
                    if domain not in constants: constants[domain] = []
                    constants[domain].append(param)
            return variables
        
        def getSingleVariableIndex(self, mln):
            paramDomains = mln.predDecl[self.predName]
            if len(paramDomains) != len(self.params): 
                raise Exception("Wrong number of parameters in '%s'; expected %d!" % (str(self), len(paramDomains)))
            varIndex = -1
            for i,param in enumerate(self.params):
                if self.logic.isVar(param[0]):
                    if varIndex == -1:
                        varIndex = i
                    else:
                        return -1
            return varIndex
    
        def _getTemplateVariables(self, mln, variables = None):
            if variables == None: variables = {}
            for i,param in enumerate(self.params):
                if param[0] == '+':
                    varname = param
                    pred = mln.predicates[self.predName]
                    domain = pred[i]
                    if varname in variables and variables[varname] != domain:
                        raise Exception("Variable '%s' bound to more than one domain" % varname)
                    variables[varname] = domain
            return variables
        
        def getPredicateNames(self, predNames=None):
            if predNames is None:
                predNames = []
            if self.predName not in predNames:
                predNames.append(self.predName)
            return predNames
    
        def ground(self, mrf, assignment, referencedGndAtoms = None, simplify=False, allowPartialGroundings=False):
            params = map(lambda x: assignment.get(x, x), self.params)
            s = "%s(%s)" % (self.predName, ",".join(params))
            gndAtom = mrf.gndAtoms.get(s, None)
            if gndAtom is not None:
                if simplify and mrf.evidence[gndAtom.idx] is not None:
                    truth = mrf.evidence[gndAtom.idx]
                    if self.negated: truth = not truth
                    return self.logic.true_false(truth)
                gndFormula = self.logic.gnd_lit(gndAtom, self.negated)
                if referencedGndAtoms != None: referencedGndAtoms.append(gndAtom.idx)
                return gndFormula
            else:
                if allowPartialGroundings:
                    return self.logic.lit(self.negated, self.predName, params)
                if any(map(lambda s: self.logic.isVar(s), params)):
                    raise Exception('Partial formula groundings are not allowed. Consider setting allowPartialGroundings=True if desired.')
                else:
                    print "\nground atoms:"
                    mrf.printGroundAtoms()
                    raise Exception("Could not ground formula containing '%s' - this atom is not among the ground atoms (see above)." % s)
    
        def getVarDomain(self, varname, mln):
            '''
            Returns the name of the domain of the given variable.
            '''
            if varname in self.params:
                idx = self.params.index(varname)
                return mln.predicates[self.predName][idx]
            return None
    
        def _groundTemplate(self, assignment):
            params = map(lambda x: assignment.get(x, x), self.params)
            if self.negated == 2: # template
                return [self.logic.lit(False, self.predName, params), self.logic.lit(True, self.predName, params)]
            else:
                return [self.logic.lit(self.negated, self.predName, params)]
            
        def simplify(self, mrf):
            if any(map(self.logic.isVar, self.params)):
                return self.logic.lit(self.negated, self.predName, self.params)
            s = "%s(%s)" % (self.predName, ",".join(self.params))
            truth = mrf.gndAtoms[s].isTrue(mrf.evidence) 
            if truth != None:
                return mrf.mln.logic.gnd_lit(mrf.gndAtoms[s], self.negated)
            else:
                if self.negated: truth = 1 - truth
                return self.logic.true_false(truth)
            
        def isTrue(self, world_values):
            return None
        
        def minTruth(self, world_values):
            return 0
        
        def maxTruth(self, world_values):
            return 1
    
    class GroundAtom(Logic.GroundAtom, Formula):
        '''
        Represents a ground atom.
        '''
        def __init__(self, predName, params, idx=None):
            self.predName = predName
            self.params = params
            self.idx = idx
    
        def isTrue(self, world_values):
            truth = world_values[self.idx]
            if truth is None: return None
            return 1 if world_values[self.idx] == 1 else 0
        
        def minTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 0
            else: return truth
        
        def maxTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 1
            else: return truth
        
        def __repr__(self):
            return str(self)
    
        def __str__(self):
            return "%s(%s)" % (self.predName, ",".join(self.params))
        
        def cstr(self, color=False):
            return "%s(%s)" % (colorize(self.predName, predicate_color, color), ",".join(self.params))
        
        def simplify(self, mrf):
            truth = self.isTrue(mrf.evidence)#mrf.evidence[self.idx]
            if truth is None:
                return self
            return self.logic.true_false(truth)
        
        def getPredicateNames(self, predNames=None):
            if predNames is None:
                predNames = []
            if self.predName not in predNames:
                predNames.append(self.predName)
            return predNames
            
            
    class GroundLit(Logic.GroundLit, Formula):
        '''
        Represents a ground literal.
        '''
        
        def __init__(self, gndAtom, negated):
            self.gndAtom = gndAtom
            self.negated = negated
    
        def isTrue(self, world_values):
            tv = self.gndAtom.isTrue(world_values)#world_values[self.gndAtom.idx]
            if tv is None: return None
            if self.negated: return (1 - tv)
            return tv
        
        def minTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 0
            else: return truth
    
        def maxTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 1
            else: return truth
    
        def __str__(self):
            return {True:"!", False:""}[self.negated] + str(self.gndAtom)
        
        def cstr(self, color=False):
            return {True:"!", False:""}[self.negated] + self.gndAtom.cstr(color)
    
        def containsGndAtom(self, idxGndAtom):
            return (self.gndAtom.idx == idxGndAtom)
        
        def getVariables(self, mln, variables=None, constants=None):
            if variables is None: variables = {}
            return variables
        
        def getConstants(self, mln, constants=None):
            if constants is None: constants = {}
            for i, c in enumerate(self.gndAtom.params):
                domName = mln.predicates[self.gndAtom.predName][i]
                values = constants.get(domName, None)
                if values is None: 
                    values = []
                    constants[domName] = values
                if not c in values: values.append(c)
            return constants
         
        def getVarDomain(self, varname, mln):
            return None
    
        def idxGroundAtoms(self, l = None):
            if l == None: l = []
            if not self.gndAtom.idx in l: l.append(self.gndAtom.idx)
            return l
    
        def getGroundAtoms(self, l = None):
            if l == None: l = []
            if not self.gndAtom in l: l.append(self.gndAtom)
            return l
        
        def toRRF(self):
            if self.negated:
                return self.logic.negation([self.gndAtom]).toRRF()
            return self.gndAtom.toRRF()
    
        def ground(self, mrf, assignment, referencedGndAtoms = None, simplify=False, allowPartialGroundings=False):
#             return self.logic.gnd_lit(self.gndAtom, self.negated)
            # always get the gnd atom from the mrf, so that
            # formulas can be transferred between different MRFs
            return self.logic.gnd_lit(mrf.gndAtoms[str(self.gndAtom)], self.negated)
    
        def simplify(self, mrf):
            f = self.gndAtom.simplify(mrf)
            if isinstance(f, Logic.TrueFalse):
                if self.negated:
                    return f.invert()
                else:
                    return f
            return self.logic.gnd_lit(self.gndAtom, self.negated)
        
        def getPredicateNames(self, predNames=None):
            if predNames is None:
                predNames = []
            if self.gndAtom.predName not in predNames:
                predNames.append(self.gndAtom.predName)
            return predNames
        
        def _getTemplateVariables(self, mln, variable = None):
            return {}
        
        def _groundTemplate(self, assignment):
            return [self.logic.gnd_lit(self.gndAtom, self.negated)]
    
    class Disjunction(Logic.Disjunction, ComplexFormula):
        '''
        Represents a disjunction of formulas.
        '''
        def __init__(self, children):
            assert len(children) >= 2
            self.children = children
    
        def __str__(self):
            return "("+" v ".join(map(str, self.children))+")"
        
        def cstr(self, color=False):
            return "(" + " v ".join(map(lambda c: c.cstr(color), self.children)) + ")"
    
        def isTrue(self, world_values):
            dontKnow = False
            for child in self.children:
                childValue = child.isTrue(world_values)
                if childValue == 1:
                    return 1
                if childValue is None:
                    dontKnow = True
            if dontKnow:
                return None
            else:
                return 0
            
        def maxTruth(self, world_values):
            mintruth = 1
            for c in self.children:
                truth = c.isTrue(world_values)
                if truth is None: continue
                if truth < mintruth: mintruth = truth
            return mintruth
        
        def minTruth(self, world_values):
            maxtruth = 0
            for c in self.children:
                truth = c.isTrue(world_values)
                if truth is None: continue
                if truth < maxtruth: maxtruth = truth
            return maxtruth
            
        def toCNF(self, level=0):
            disj = []
            str_disj = []
            conj = []
            # convert children to CNF and group by disjunction/conjunction; flatten nested disjunction, remove duplicates, check for tautology
            for child in self.children:
                c = child.toCNF(level+1) # convert child to CNF -> must be either conjunction of clauses, disjunction of literals, literal or boolean constant
                if isinstance(c, Logic.Conjunction):
                    conj.append(c)
                else:
                    if isinstance(c, Logic.Disjunction):
                        l = c.children
                    else: # literal or boolean constant
                        l = [c]
                    for x in l:
                        # if the literal is always true, the disjunction is always true; if it's always false, it can be ignored
                        if isinstance(c, Logic.TrueFalse):
                            if x.isTrue():
                                return self.logic.true_false(1)
                            else:
                                continue
                        # it's a regular literal: check if the negated literal is already among the disjuncts
                        s = str(x)
                        if s[0] == '!':
                            if s[1:] in str_disj:
                                return self.logic.true_false(1)
                        else:
                            if ("!" + s) in str_disj:
                                return self.logic.true_false(1)
                        # check if the literal itself is not already there and if not, add it
                        if not s in str_disj:
                            disj.append(x)
                            str_disj.append(s)
            # if there are no conjunctions, this is a flat disjunction or unit clause
            if len(conj) == 0: 
                if len(disj) >= 2:
                    return self.logic.disjunction(disj)
                else:
                    return disj[0]
            # there are conjunctions among the disjuncts
            # if there is only one conjunction and no additional disjuncts, we are done
            if len(conj) == 1 and len(disj) == 0:
                return conj[0]
            # otherwise apply distributivity
            # use the first conjunction to distribute: (C_1 ^ ... ^ C_n) v RD = (C_1 v RD) ^ ... ^  (C_n v RD)
            # - C_i = conjuncts[i]
            conjuncts = conj[0].children 
            # - RD = disjunction of the elements in remaining_disjuncts (all the original disjuncts except the first conjunction)
            remaining_disjuncts = disj + conj[1:] 
            # - create disjunctions
            disj = []
            for c in conjuncts:
                disj.append(self.logic.disjunction([c] + remaining_disjuncts))
            return self.logic.conjunction(disj).toCNF(level + 1)
    
        def toNNF(self, level = 0):
            disjuncts = []
            for child in self.children:
                c = child.toNNF(level+1)
                if isinstance(c, Logic.Disjunction): # flatten nested disjunction
                    disjuncts.extend(c.children)
                else:
                    disjuncts.append(c)
            return self.logic.disjunction(disjuncts)
    
        def simplify(self, mrf):
            sf_children = []
            for child in self.children:
                child = child.simplify(mrf)
                if isinstance(child, Logic.TrueFalse):
                    if child.isTrue():
                        return self.logic.true_false(1)
                else:
                    sf_children.append(child)
            if len(sf_children) == 1:
                return sf_children[0]
            elif len(sf_children) >= 2:
                return self.logic.disjunction(sf_children)
            else:
                return self.logic.true_false(0)
            
    class Conjunction(Logic.Conjunction, ComplexFormula):
        '''
        Represents a logical conjunction.
        '''
        
        def __init__(self, children):
            assert len(children) >= 2
            self.children = children
    
        def __str__(self):
            return "("+" ^ ".join(map(str, self.children))+")"
    
        def cstr(self, color=False):
            return "(" + " ^ ".join(map(lambda c: c.cstr(color), self.children)) + ")"
    
        def isTrue(self, world_values):
            dontKnow = False
            for child in self.children:
                childValue = child.isTrue(world_values)
                if childValue is 0:
                    return 0.
                if childValue is None:
                    dontKnow = True
            if dontKnow:
                return None
            else:
                return 1.
            
        def maxTruth(self, world_values):
            mintruth = 1
            for c in self.children:
                truth = c.isTrue(world_values)
                if truth is None: continue
                if truth < mintruth: mintruth = truth
            return mintruth
        
        def minTruth(self, world_values):
            maxtruth = 0
            for c in self.children:
                truth = c.isTrue(world_values)
                if truth is None: continue
                if truth < maxtruth: maxtruth = truth
            return maxtruth
            
        def toCNF(self, level=0):
            clauses = []
            litSets = []
            for child in self.children:
                c = child.toCNF(level+1)
                if isinstance(c, Logic.Conjunction): # flatten nested conjunction
                    l = c.children
                else:
                    l = [c]
                for clause in l: # (clause is either a disjunction, a literal or a constant)
                    # if the clause is always true, it can be ignored; if it's always false, then so is the conjunction
                    if isinstance(clause, Logic.TrueFalse):
                        if clause.isTrue() == 1:
                            continue
                        elif clause.isTrue() == 0:
                            return self.logic.true_false(0)
                    # get the set of string literals
                    if hasattr(clause, "children"):
                        litSet = set(map(str, clause.children))
                    else: # unit clause
                        litSet = set([str(clause)])
                    # check if the clause is equivalent to another (subset/superset of the set of literals) -> always keep the smaller one
                    doAdd = True
                    i = 0
                    while i < len(litSets):
                        s = litSets[i]
                        if len(litSet) < len(s):
                            if litSet.issubset(s):
                                del litSets[i]
                                del clauses[i]
                                continue
                        else:
                            if litSet.issuperset(s):
                                doAdd = False
                                break
                        i += 1
                    if doAdd:
                        clauses.append(clause)
                        litSets.append(litSet)
            if len(clauses) == 1:
                return clauses[0]
            return self.logic.conjunction(clauses)
        
        def toNNF(self, level = 0):
            conjuncts = []
            for child in self.children:
                c = child.toNNF(level+1)
                if isinstance(c, Logic.Conjunction): # flatten nested conjunction
                    conjuncts.extend(c.children)
                else:
                    conjuncts.append(c)
            return self.logic.conjunction(conjuncts)
        
        def simplify(self, mrf):
            sf_children = []
            for child in self.children:
                child = child.simplify(mrf)
                if isinstance(child, Logic.TrueFalse):
                    if not child.isTrue():
                        return self.logic.true_false(0)
                else:
                    sf_children.append(child)
            if len(sf_children) == 1:
                return sf_children[0]
            elif len(sf_children) >= 2:
                return self.logic.conjunction(sf_children)
            else:
                return self.logic.true_false(1)
                
    class Implication(Logic.Implication, ComplexFormula):
        
        def __init__(self, children):
            assert len(children) == 2
            self.children = children
    
        def __str__(self):
            return "(" + str(self.children[0]) + " => " + str(self.children[1]) + ")"
        
        def cstr(self, color=False):
            return "(" + self.children[0].cstr(color) + " => " + self.children[1].cstr(color) + ")"
    
        def isTrue(self, world_values):
            ant = self.children[0].isTrue(world_values)
            cons = self.children[1].isTrue(world_values)
            if ant is 0 or cons is 1:
                return 1
            if ant is None or cons is None:
                return None
            return 0
        
        def toCNF(self, level=0):
            return self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]]).toCNF(level+1)
        
        def toNNF(self, level=0):
            return self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]]).toNNF(level+1)
        
        def toRRF(self):
            return self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]]).toRRF()
        
        def simplify(self, mrf):
            return self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]]).simplify(mrf)
    
    class Biimplication(Logic.Biimplication, ComplexFormula):
        '''
        Represents a bi-implication.
        '''
        
        def __init__(self, children):
            assert len(children) == 2
            self.children = children
    
        def __str__(self):
            return "(" + str(self.children[0]) + " <=> " + str(self.children[1]) + ")"
        
        def cstr(self, color=False):
            return "(" + self.children[0].cstr(color) + " <=> " + self.children[1].cstr(color) + ")"
    
        def isTrue(self, world_values):
            c1 = self.children[0].isTrue(world_values)
            c2 = self.children[1].isTrue(world_values)
            if c1 is None or c2 is None:
                return None
            return 1 if (c1 == c2) else 0
        
        def toCNF(self, level=0):
            return self.logic.conjunction([self.logic.implication([self.children[0], self.children[1]]), self.logic.implication([self.children[1], self.children[0]])]).toCNF(level+1)
        
        def toNNF(self, level = 0):
            return self.logic.conjunction([self.logic.implication([self.children[0], self.children[1]]), self.logic.implication([self.children[1], self.children[0]])]).toNNF(level+1)
        
        def toRRF(self):
            return self.logic.conjunction([self.logic.implication([self.children[0], self.children[1]]), self.logic.Implication([self.children[1], self.children[0]])]).toRRF()
    
        def simplify(self, mrf):
            c1 = self.logic.disjunction([self.logic.negation([self.children[0]]), self.children[1]])
            c2 = self.logic.disjunction([self.children[0], self.logic.negation([self.children[1]])])
            return self.logic.conjunction([c1,c2]).simplify(mrf)
        
        
    class Negation(Logic.Negation, ComplexFormula):
        '''
        Represents a negation of a complex formula.
        '''
        
        def __init__(self, children):
            assert len(children) == 1
            self.children = children
    
        def __str__(self):
            return "!(" + str(self.children[0]) + ")"
        
        def cstr(self, color=False):
            return "!(" + self.children[0].cstr(color) + ")"
    
        def isTrue(self, world_values):
            childValue = self.children[0].isTrue(world_values)
            if childValue is None:
                return None
            return 1 - childValue
        
        def toCNF(self, level=0):
            # convert the formula that is negated to negation normal form (NNF), 
            # so that if it's a complex formula, it will be either a disjunction
            # or conjunction, to which we can then apply De Morgan's law.
            # Note: CNF conversion would be unnecessarily complex, and, 
            # when the children are negated below, most of it would be for nothing!
            child = self.children[0].toNNF(level+1)
            # apply negation to child (pull inwards)
            if hasattr(child, 'children'):
                neg_children = []
                for c in child.children:
                    neg_children.append(self.logic.negation([c]).toCNF(level+1))
                if isinstance(child, Logic.Conjunction):
                    return self.logic.disjunction(neg_children).toCNF(level+1)
                elif isinstance(child, Logic.Disjunction):
                    return self.logic.conjunction(neg_children).toCNF(level+1)
                elif isinstance(child, Logic.Negation):
                    return c.toCNF(level+1)
                else:
                    raise Exception("Unexpected child type %s while converting '%s' to CNF!" % (str(type(child)), str(self)))
            elif isinstance(child, Logic.Lit):
                return self.logic.lit(not child.negated, child.predName, child.params)
            elif isinstance(child, Logic.GroundLit):
                return self.logic.gnd_lit(child.gndAtom, not child.negated)
            elif isinstance(child, Logic.TrueFalse):
                return self.logic.true_false(1 - child.value)
            elif isinstance(child, Logic.Equality):
                return self.logic.equality(child.params, not child.negated)
            else:
                raise Exception("CNF conversion of '%s' failed (type:%s)" % (str(self), str(type(child))))
        
        def toNNF(self, level = 0):
            # child is the formula that is negated
            child = self.children[0].toNNF(level+1)
            # apply negation to the children of the formula that is negated (pull inwards)
            # - complex formula (should be disjunction or conjunction at this point), use De Morgan's law
            if hasattr(child, 'children'): 
                neg_children = []
                for c in child.children:
                    neg_children.append(self.logic.negation([c]).toNNF(level+1))
                if isinstance(child, Logic.Conjunction): # !(A ^ B) = !A v !B
                    return self.logic.disjunction(neg_children).toNNF(level+1)
                elif isinstance(child, Logic.Disjunction): # !(A v B) = !A ^ !B
                    return self.logic.conjunction(neg_children).toNNF(level+1)
                elif isinstance(child, Logic.Negation):
                    return c.toNNF(level+1)
                # !(A => B) = A ^ !B     
                # !(A <=> B) = (A ^ !B) v (B ^ !A)
                else:
                    raise Exception("Unexpected child type %s while converting '%s' to NNF!" % (str(type(child)), str(self)))
            # - non-complex formula, i.e. literal or constant
            elif isinstance(child, Logic.Lit):
                return self.logic.lit(not child.negated, child.predName, child.params)
            elif isinstance(child, Logic.GroundLit):
                return self.logic.gnd_lit(child.gndAtom, not child.negated)
            elif isinstance(child, Logic.TrueFalse):
                return self.logic.true_false(1 - child.value)
            elif isinstance(child, Logic.Equality):
                return self.logic.equality(child.params, not child.negated)
            else:
                raise Exception("NNF conversion of '%s' failed (type:%s)" % (str(self), str(type(child))))
    
        def simplify(self, mrf):
            f = self.children[0].simplify(mrf)
            if isinstance(f, Logic.TrueFalse):
                return f.invert()
            else:
                return self.logic.negation([f])
            
    class Exist(Logic.Exist, ComplexFormula):
        '''
        Existential quantifier.
        '''
        
        def __init__(self, variables, formula):
            self.children = [formula]
            self.vars = variables
    
        def __str__(self):
            return "EXIST " + ", ".join(self.vars) + " (" + str(self.children[0]) + ")"
#     
        def cstr(self, color=False):
            return colorize('EXIST ', predicate_color, color) + ', '.join(self.vars) + ' (' + self.children[0].cstr(color) + ')'
    
        def getVariables(self, mln, variables = None, constants = None):
            if variables == None: 
                variables = {}
            # get the child's variables:
            newvars = self.children[0].getVariables(mln, None, constants)
            # remove the quantified variable(s)
            for var in self.vars:
                try:
                    del newvars[var]
                except:
                    raise Exception("Variable '%s' in '%s' not bound to a domain!" % (var, str(self)))
            # add the remaining ones and return
            variables.update(newvars)
            return variables
             
        def ground(self, mrf, assignment, referencedGroundAtoms = None, allowPartialGroundings=False, simplify=False):
            assert len(self.children) == 1
            # find out variable domains
            variables = {}
            for var in self.vars:
                domName = None
                for child in self.children:
                    domName = child.getVarDomain(var, mrf.mln)
                    if domName is not None:
                        break
                if domName is None:
                    raise Exception("Could not obtain domain of variable '%s', which is part of '%s')" % (var, str(self)))
                variables[var] = domName
            # ground
            gndings = []
            self._ground(self.children[0], variables, assignment, gndings, mrf, referencedGroundAtoms, allowPartialGroundings=allowPartialGroundings)
            if len(gndings) == 1:
                return gndings[0]
            disj = self.logic.disjunction(gndings)
            if simplify:
                return disj.simplify(mrf)
            else:
                return disj
                 
        def _ground(self, formula, variables, assignment, gndings, mrf, referencedGroundAtoms=None, allowPartialGroundings=False):
            # if all variables have been grounded...
            if variables == {}:
                gndFormula = formula.ground(mrf, assignment, referencedGroundAtoms, allowPartialGroundings=allowPartialGroundings)
                gndings.append(gndFormula)
                return
            # ground the first variable...
            varname,domName = variables.popitem()
            for value in mrf.domains[domName]: # replacing it with one of the constants
                assignment[varname] = value
                # recursive descent to ground further variables
                self._ground(formula, dict(variables), assignment, gndings, mrf, allowPartialGroundings=allowPartialGroundings)
         
        def toCNF(self,l=0):
            raise Exception("'%s' cannot be converted to CNF. Ground this formula first!" % str(self))
      
        def isTrue(self, w):
            raise Exception("'%s' does not implement isTrue()")
     
    
    class Equality(Logic.Equality, ComplexFormula):
        '''
        Represents (in)equality constraints between two symbols.
        '''
        
        def __init__(self, params, negated=False):
            assert len(params) == 2
            self.params = params
            self.negated = negated
    
        def __str__(self):
            return "%s%s%s" % (str(self.params[0]), '=/=' if self.negated else '=', str(self.params[1]))
        
        def cstr(self, color=False):
            return str(self)
    
        def ground(self, mrf, assignment, referencedGndAtoms = None, simplify=False, allowPartialGroundings=False):
            # if the parameter is a variable, do a lookup (it must be bound by now), 
            # otherwise it's a constant which we can use directly
            params = map(lambda x: assignment.get(x, x), self.params) 
            if self.logic.isVar(params[0]) or self.logic.isVar(params[1]):
                if allowPartialGroundings:
                    return self.logic.equality(params, self.negated)
                else: raise Exception("At least one variable was not grounded in '%s'!" % str(self))
            if simplify:
                equal = (params[0] == params[1])
                return self.logic.true_false(1 if {True: not equal, False: equal}[self.negated] else 0)
            else:
                return self.logic.equality(params, self.negated)
    
        def _groundTemplate(self, assignment):
            return [self.logic.equality(self.params, negated=self.negated)]
        
        def _getTemplateVariables(self, mln, variables = None):
            return variables
        
        def getVariables(self, mln, variables = None, constants = None):        
            if variables is None:
                variables = {}
#             if constants is not None:
#                 # determine type of constant appearing in expression such as "x=Foo"
#                 for i, p in enumerate(self.params):
#                     other = self.params[(i + 1) % 2]
#                     if self.logic.isConstant(p) and self.logic.isVar(other):
#                         domain = variables.get(other)
#                         if domain is None:
#                             raise Exception("Type of constant '%s' could not be determined" % p)
#                         if domain not in constants: constants[domain] = []
#                         constants[domain].append(p)
            return variables
        
        def getVarDomain(self, varname, mln):
            return None
        
        def getPredicateNames(self, predNames=None):
            if predNames is None:
                predNames = []
            return predNames
        
        def isTrue(self, world_values):
            if any(map(self.logic.isVar, self.params)):
                return None
            equals = 1 if (self.params[0] == self.params[1]) else 0
            return (1 - equals) if self.negated else equals
        
        def maxTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 1
            else: return truth 
        
        def minTruth(self, world_values):
            truth = self.isTrue(world_values)
            if truth is None: return 0
            else: return truth 
        
        
        def simplify(self, mrf):
            truth = self.isTrue(mrf.evidence) 
            if truth != None: return self.logic.true_false(truth)
            return self.logic.equality(list(self.params), negated=self.negated)
    
            
    class TrueFalse(Logic.TrueFalse, Formula):
        '''
        Represents the constants true and false.
        '''
        
        def __init__(self, value):
            assert value == 0 or value == 1
            self.value = value
        
        def __str__(self):
            return str(True if self.value == 1 else False)
    
        def cstr(self, color=False):
            return str(self)
    
        def isTrue(self, world_values = None):
            return self.value
        
        def minTruth(self, world_values=None):
            return self.value
        
        def maxTruth(self, world_values=None):
            return self.value
    
        def invert(self):
            return self.logic.true_false(1 - self.value)
        
        def simplify(self, mrf):
            return self
        
        def getVariables(self, mln, variables = None, constants=None):
            if variables is None:
                return {}
            return variables
        
        def ground(self, mln, assignment, referencedAtoms = None, simplify=False, allowPartialGroundings=False):
            return self.logic.true_false(self.value)
    
    
    class NonLogicalConstraint(Logic.NonLogicalConstraint, Constraint):
        '''
        A constraint that is not somehow made up of logical connectives and (ground) atoms.
        '''
        
        def getTemplateVariants(self, mln):
            # non logical constraints are never templates; therefore, there is just one variant, the constraint itself
            return [self]
        
        def isLogical(self):
            return False
        
        def negate(self):
            raise Exception("%s does not implement negate()" % str(type(self)))
        
        
    class CountConstraint(Logic.CountConstraint, NonLogicalConstraint):
        '''
        A constraint that tests the number of relation instances against an integer.
        '''
        
        def __init__(self, predicate, predicate_params, fixed_params, op, count):
            '''op: an operator; one of "=", "<=", ">=" '''
            self.literal = self.logic.lit(False, predicate, predicate_params)
            self.fixed_params = fixed_params
            self.count = count
            if op == "=": op = "=="
            self.op = op
        
        def __str__(self):
            op = self.op
            if op == "==": op = "="
            return "count(%s | %s) %s %d" % (str(self.literal), ", ".join(self.fixed_params), op, self.count)
        
        def cstr(self, color=False):
            return str(self)
        
        def iterGroundings(self, mrf, simplify=False):
            a = {}
            other_params = []
            for param in self.literal.params:
                if param[0].isupper():
                    a[param] = param
                else:
                    if param not in self.fixed_params:
                        other_params.append(param)
            #other_params = list(set(self.literal.params).difference(self.fixed_params))
            # for each assignment of the fixed parameters...
            for assignment in self._iterAssignment(mrf, list(self.fixed_params), a):
                gndAtoms = []
                # generate a count constraint with all the atoms we obtain by grounding the other params
                for full_assignment in self._iterAssignment(mrf, list(other_params), assignment):
                    gndLit = self.literal.ground(mrf, full_assignment, None)
                    gndAtoms.append(gndLit.gndAtom)
                yield self.logic.gnd_count_constraint(gndAtoms, self.op, self.count), []
            
        def _iterAssignment(self, mrf, variables, assignment):
            '''iterates over all possible assignments for the given variables of this constraint's literal
                    variables: the variables that are still to be grounded'''
            # if all variables have been grounded, we have the complete assigment
            if len(variables) == 0:
                yield dict(assignment)
                return
            # otherwise one of the remaining variables in the list...
            varname = variables.pop()
            domName = self.literal.getVarDomain(varname, mrf.mln)
            for value in mrf.domains[domName]: # replacing it with one of the constants
                assignment[varname] = value
                # recursive descent to ground further variables            
                for a in self._iterAssignment(mrf, variables, assignment):
                    yield a
        
        def getVariables(self, mln, variables = None, constants = None):
            if constants is not None:
                self.literal.getVariables(mln, variables, constants)
            return variables
                
    class GroundCountConstraint(Logic.GroundCountConstraint, NonLogicalConstraint):
        def __init__(self, gndAtoms, op, count):
            self.gndAtoms = gndAtoms
            self.count = count
            self.op = op
        
        def isTrue(self, world_values):
            c = 0
            for ga in self.gndAtoms:
                if(world_values[ga.idx]):
                    c += 1
            return eval("c %s self.count" % self.op)
    
        def __str__(self):
            op = self.op
            if op == "==": op = "="
            return "count(%s) %s %d" % (";".join(map(str, self.gndAtoms)), op, self.count)
        
        def cstr(self, color=False):
            op = self.op
            if op == "==": op = "="
            return "count(%s) %s %d" % (";".join(map(lambda c: c.cstr(color), self.gndAtoms)), op, self.count)
    
        def negate(self):
            if self.op == "==":
                self.op = "!="
            elif self.op == "!=":
                self.op = "=="
            elif self.op == ">=":
                self.op = "<="
                self.count -= 1
            elif self.op == "<=":
                self.op = ">="
                self.count += 1
        
        def idxGroundAtoms(self, l = None):
            if l is None: l = []
            for ga in self.gndAtoms:
                l.append(ga.idx)
            return l
    
        def getGroundAtoms(self, l = None):
            if l is None: l = []
            for ga in self.gndAtoms:
                l.append(ga)
            return l

    
    @logic_factory
    def conjunction(self, *args, **kwargs):
        return FirstOrderLogic.Conjunction(*args, **kwargs)
    
    @logic_factory 
    def disjunction(self, *args, **kwargs):
        return FirstOrderLogic.Disjunction(*args, **kwargs)
    
    @logic_factory
    def negation(self, *args, **kwargs):
        return FirstOrderLogic.Negation(*args, **kwargs)
    
    @logic_factory 
    def implication(self, *args, **kwargs):
        return FirstOrderLogic.Implication(*args, **kwargs)
    
    @logic_factory
    def biimplication(self, *args, **kwargs):
        return FirstOrderLogic.Biimplication(*args, **kwargs)
    
    @logic_factory
    def equality(self, *args, **kwargs):
        return FirstOrderLogic.Equality(*args, **kwargs)
     
    @logic_factory
    def exist(self, *args, **kwargs):
        return FirstOrderLogic.Exist(*args, **kwargs)
    
    @logic_factory
    def gnd_atom(self, *args, **kwargs):
        return FirstOrderLogic.GroundAtom(*args, **kwargs)
    
    @logic_factory
    def lit(self, *args, **kwargs):
        return FirstOrderLogic.Lit(*args, **kwargs)
    
    @logic_factory
    def gnd_lit(self, *args, **kwargs):
        return FirstOrderLogic.GroundLit(*args, **kwargs)
    
    @logic_factory
    def count_constraint(self, *args, **kwargs):
        return FirstOrderLogic.CountConstraint(*args, **kwargs)
    
    @logic_factory
    def true_false(self, *args, **kwargs):
        return FirstOrderLogic.TrueFalse(*args, **kwargs)
    

# this is a little hack to make nested classes pickleable
Constraint = FirstOrderLogic.Constraint
Formula = FirstOrderLogic.Formula
ComplexFormula = FirstOrderLogic.ComplexFormula
Conjunction = FirstOrderLogic.Conjunction
Disjunction = FirstOrderLogic.Disjunction
Lit = FirstOrderLogic.Lit
GroundLit = FirstOrderLogic.GroundLit
GroundAtom = FirstOrderLogic.GroundAtom
Equality = FirstOrderLogic.Equality
Implication = FirstOrderLogic.Implication
Biimplication = FirstOrderLogic.Biimplication
Negation = FirstOrderLogic.Negation
Exist = FirstOrderLogic.Exist
TrueFalse = FirstOrderLogic.TrueFalse
NonLogicalConstraint = FirstOrderLogic.NonLogicalConstraint
CountConstraint = FirstOrderLogic.CountConstraint
GroundCountConstraint = FirstOrderLogic.GroundCountConstraint
