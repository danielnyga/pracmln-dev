# -*- coding: utf-8 -*-
#
# Markov Logic Networks
#
# (C) 2012-2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
# (C) 2006-2011 by Dominik Jain (jain@cs.tum.edu)
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

from database import readDBFromFile
from logic import FirstOrderLogic, FuzzyLogic
import copy
from utils import dict_union, comment_color, predicate_color, weight_color,\
    colorize

from debug import DEBUG
import praclog
import logging
from string import whitespace
import sys
import os
import traceback
from pyparsing import ParseException

from grounding import * 
from learning import *
from inference import *

import platform
from methods import InferenceMethods, LearningMethods
from util import mergeDomains, strFormula, stripComments
from mrf import MRF
import re
from errors import MLNParsingError


if platform.architecture()[0] == '32bit':
    try:
        if not DEBUG:
            import psyco # Don't use Psyco when debugging! @UnresolvedImport
            psyco.full()
    except:
        logging.getLogger(__name__).critical("Note: Psyco (http://psyco.sourceforge.net) was not loaded. On 32bit systems, it is recommended to install it for improved performance.\n")

sys.setrecursionlimit(10000)

'''
Your MLN files may contain:
    - domain declarations, e.g.
            domainName = {value1, value2, value3}
    - predicate declarations, e.g.
            pred1(domainName1, domainName2)
        mutual exclusiveness and exhaustiveness may be declared simultaneously, e.g.
        pred1(a,b!) to state that for every constant value that variable a can take on, there is exactly one value that b can take on
    - formulas, e.g.
            12   cloudy(d)
    - C++-style comments (i.e. // and /* */) anywhere

The syntax of .mln files is mostly compatible to the Alchemy system (see manual of the Alchemy system)
with the following limitations:
    - one line per definition, no line breaks allowed
    - all formulas must be preceded by a weight, which can be expressed as an arithmetic expression such as "1.0/3.0" or "log(0.5)"
      note that formulas are not decomposed into clauses but processed as is.
      operators (in order of precedence; use parentheses to change precendence):
              !   negation
              v   disjunction
              ^   conjunction
              =>  implication
              <=> biimplication
      Like Alchemy, we support the prefix operators * on literals and + on variables to specify templates for formulas.
    - no support for functions

As a special construct of our implementation, an MLN file may contain constraints of the sort
    P(foo(x, Bar)) = 0.5
i.e. constraints on formula probabilities that cause weights to be automatically adjusted to conform to the constraint.
Note that the MLN must contain the corresponding formula.

deprecated features:

We support an alternate representation where the parameters are factors between 0 and 1 instead of regular weights.
To use this representation, make use of infer2 rather than infer to compute probabilities.
To learn factors rather than regular weights, use "LL_fac" rather than "LL" as the method you supply to learnwts.
(pseudolikelihood is currently unsupported for learning such representations)
'''

# -- Markov logic network

class MLN(object):
    '''
    Represents a Markov logic network and/or a ground Markov network

    members:
        blocks:
            dict: predicate name -> list of booleans that indicate which arguments 
            of the pred are functionally determined by the others (one boolean per
            argument, True = is functionally determined)
        closedWorldPreds:
            list of predicates that are assumed to be closed-world (for inference)
        formulas:
            list of formula objects
        predicates:
            dict: predicate name -> list of domain names that apply to the predicate's parameters
        worldCode2Index:
            dict that maps a world's identification code to its index in self.worlds
        worlds
            list of possible worlds, each entry is a dict with
                'values' -> list of booleans - one for each gnd atom
        allSoft:
            for soft evidence learning: flag,
              if true: compute counts for normalization worlds using soft counts
              if false: compute counts for normalization worlds using hard counts (boolean worlds)
        learnWtsMode
    '''

    def __init__(self, logic='FirstOrderLogic', grammar='PRACGrammar', defaultInferenceMethod=InferenceMethods.MCSAT, parameterType='weights', verbose=False):
        '''
        Constructs an empty MLN object. For reading an MLN object 
        from an .mln file, see readMLNFromFile (below).
        '''
        
        # instantiate the logic and grammar
        logic_str = '%s("%s")' % (logic, grammar)
        self.logic = eval(logic_str)
        
        self.predicates = {}
        self.domains = {}
        self.formulas = []
        
        self.blocks = {}
        self.domDecls = []
        self.probreqs = []
        self.posteriorProbReqs = []
        self.defaultInferenceMethod = defaultInferenceMethod
        self.probabilityFittingInferenceMethod = InferenceMethods.Exact
        self.probabilityFittingThreshold = 0.002 # maximum difference between desired and computed probability
        self.probabilityFittingMaxSteps = 20 # maximum number of steps to run iterative proportional fitting
        self.parameterType = parameterType
        self.formulaGroups = []
        self.closedWorldPreds = []
        self.learnWtsMode = None
        self.templateIdx2GroupIdx = {}
        self.vars = {}
        self.allSoft = False
        self.uniqueFormulaExpansions = {}
        self.fixedWeightFormulas = []
        self.fixedWeightTemplateIndices = []

    def duplicate(self):
        '''
        Returns a deep copy of this MLN, which is not yet materialized.
        '''
        return copy.deepcopy(self)
    
    
    def get_predicate(self, pred_name):
        '''
        Returns the predicate name, the domains of arguments and block information about
        the predicate with the given name, or None if there is none.
        '''
        domains = self.predicates.get(pred_name, None)
        if domains is None:
            return None
        blocks = self.blocks.get(pred_name, None)
        if blocks is None:
            blocks = [False] * len(domains)
        return pred_name, domains, blocks
    
    
    def iter_predicates(self):
        '''
        Yields the predicates defined by this MLN according to the ``get_predicate()`` method.
        '''
        for pred in self.predicates:
            yield self.get_predicate(pred)
    
    
    def update_predicates(self, mln):
        '''
        Merges the predicate definitions of this MLN with the definitions
        of the given one.
        '''
        for pred in mln.iter_predicates():
            self.declarePredicate(*pred)
    

    def declarePredicate(self, name, domains, mutex=None):
        '''
        Adds a predicate declaration to the MLN:
        - name:        name of the predicate (string)
        - domains:     list of domain names of arguments
        - mutex:       list of True/False values of args determining whether or not they are mutex constraints.
                       Will be expanded to ``[False] * len(domains)`` if None.
        '''
        pred = self.get_predicate(name)
        if mutex is None:
            mutex = [False] * len(domains)
        assert len(domains) == len(mutex)
        if pred is not None:
            _, old_domains, old_mutex = pred
            if old_domains != domains or old_mutex != mutex:
                raise Exception('Contradictory predicate definitions: %s <--> %s' % (predicate_declaration_string(name, domains, mutex), 
                                                                                     predicate_declaration_string(name, old_domains, old_mutex)))
        else:
            self.predicates[name] = domains
            self.blocks[name] = mutex
            for dom in domains:
                if dom not in self.domains:
                    self.domains[dom] = []

            
    def addFormula(self, formula, weight=0, hard=False, fixWeight=False):
        '''
        Add a formula to this MLN. The respective domains of constants
        are updated, if necessary.
        '''
        self._addFormula(formula, self.formulas, weight, hard, fixWeight)
    
    
    def _addFormula(self, formula, formulaSet, weight=0, hard=False, fixWeight=False):
        '''
        Adds the given formula to the MLN and extends the respective domains, if necessary.
        - formula:    a FOL.Formula object or a string
        - weight:     weight of the formula
        - hard:       determines if the formula is hard
        - fixWeight:  determines if the weight of the formula is fixed
        '''
        if type(formula) is str:
            formula = self.logic.parseFormula(formula)
        formula.weight = weight
        formula.isHard = hard
        idxTemplate = len(formulaSet)
        if fixWeight:
            self.fixedWeightTemplateIndices.append(idxTemplate)
        formulaSet.append(formula)
        # extend domains
        constants = {}
        formula.getConstants(self, constants)
        for domain, constants in constants.iteritems():
            for c in constants: 
                self.addConstant(domain, c)
        
                
    def infer(self, method, queries=None, evidence_db=None, **params):
        log = logging.getLogger(self.__class__.__name__)
        self.defaultInferenceMethod = method
        
        # apply closed world assumption
        if params.get('closedWorld', False):
            queries = filter(lambda x: x != "", map(str.strip, queries.split(",")))
            cwPreds = set(params.get('cwPreds', []))
            for p in self.predicates:
                if p not in queries:
                    cwPreds.add(p)
            params['cwPreds'] = cwPreds
        self.setClosedWorldPred(*params.get('cwPreds', []))
        if evidence_db is None:
            evidence_db = Database(self)
        materialized_mln = self.materializeFormulaTemplates([evidence_db])
        mrf = materialized_mln.groundMRF(evidence_db, simplify=True, groundingMethod='FastConjunctionGrounding', **params)
        resultDict = mrf.infer(what=queries, given=None, **params)
        log.debug(resultDict)
        result_db = Database(self)
        for atom in sorted(resultDict):
            value = resultDict[atom]
            result_db.addGroundAtom(atom, value)
            if value > 0:
                log.info("%.3f    %s" % (value, atom))
        return result_db.union(None, evidence_db) 
        
                
    def materializeFormulaTemplates(self, dbs, verbose=False):
        '''
        Expand all formula templates.
        - dbs: list of `Database` objects
        '''
        log = logging.getLogger(self.__class__.__name__)
        log.info("materializing formula templates...")
        
#         for f in self.formulas:
#             log.info(f.cstr(True) + ' ' + str(type(f)))
        newMLN = self.duplicate()
        # obtain full domain with all objects 
        fullDomain = mergeDomains(self.domains, *[db.domains for db in dbs])
        log.debug('domains: %s' % fullDomain)
        # collect the admissible formula templates. templates might be not
        # admissible since the domain of a template variable might be empty.
        for ft in list(newMLN.formulas):
            domNames = ft.getVariables(self).values()
            if any([not domName in fullDomain for domName in domNames]):
                log.debug('Discarding formula template %s, since it cannot be grounded (domain(s) %s empty).' % \
                    (strFormula(ft), ','.join([d for d in domNames if d not in fullDomain])))
                newMLN.formulas.remove(ft)
        
        # collect the admissible predicates. a predicate may become inadmissible
        # if either the domain of one of its arguments is empty or there is
        # no formula containing the respective predicate.
        predicatesUsed = set()
        for f in newMLN.formulas:
            predicatesUsed.update(f.getPredicateNames())
        for pred, _ in self.predicates.iteritems():
            remove = False
            if any([not dom in fullDomain for dom in self.predicates[pred]]):
                log.debug('Discarding predicate %s, since it cannot be grounded.' % (pred))
                remove = True
            if pred not in predicatesUsed:
                log.debug('Discarding predicate %s, since it is unused.' % pred)
                remove = True
            if remove: del newMLN.predicates[pred]
        
        # permanently transfer domains of variables that were expanded from templates
        for ft in newMLN.formulas:
            domNames = ft._getTemplateVariables(self).values()
            for domName in domNames:
                newMLN.domains[domName] = fullDomain[domName]
                
        newMLN._materializeFormulaTemplates()
        return newMLN

    def _materializeFormulaTemplates(self, verbose=False):
        '''
        CAUTION: This method has side effects.
        TODO: Draw this method into materializeFormulaTemplates.
        '''
        templateIdx2GroupIdx = self.templateIdx2GroupIdx
        fixedWeightTemplateIndices = self.fixedWeightTemplateIndices
        templates = self.formulas
        self.formulas = []
        
        # materialize formula templates
        idxGroup = None
        prevIdxGroup = None
        group = []
        for idxTemplate, tf in enumerate(templates):
            idxGroup = templateIdx2GroupIdx.get(idxTemplate)
            if idxGroup != None:
                if idxGroup != prevIdxGroup: # starting new group
                    self.formulaGroups.append(group)
                    group = []
                prevIdxGroup = idxGroup
            # get template variants
            fl = tf.getTemplateVariants(self)
            # add them to the list of formulas and set index
            for f in fl:
                f.weight = tf.weight
                f.isHard = tf.isHard
                if f.weight is None:
                    self.hard_formulas.append(f)
                idxFormula = len(self.formulas)
                self.formulas.append(f)
                f.idxFormula = idxFormula
                # add the formula indices to the group if any
                if idxGroup != None:
                    group.append(idxFormula)
                # fix weight of formulas
                if idxTemplate in fixedWeightTemplateIndices:
                    self.fixedWeightFormulas.append(f)
        if group != []: # add the last group (if any)
            self.formulaGroups.append(group)

    def addConstant(self, domainName, constant):
        if domainName not in self.domains: self.domains[domainName] = []
        dom = self.domains[domainName]
        if constant not in dom: dom.append(constant)

    def _substVar(self, matchobj):
        varName = matchobj.group(0)
        if varName not in self.vars:
            raise Exception("Unknown variable '%s'" % varName)
        return self.vars[varName]

    def groundMRF(self, db, simplify=False, groundingMethod='DefaultGroundingFactory', cwAssumption=False, **params):
        '''
        Creates and returns a ground Markov Random Field for the given database
        - db: database filename (string) or Database object
        '''
        mrf = MRF(self, db, groundingMethod=groundingMethod, cwAssumption=cwAssumption, simplify=simplify, **params)
        return mrf

    def combineOverwrite(self, domain, verbose=False, groundFormulas=True):
        '''
            combines the existing domain (if any) with the given one
                domain: a dictionary with domainName->list of string constants to add
        '''
        domNames = set(self.domains.keys() + domain.keys())
        for domName in domNames:
            a = self.domains.get(domName, [])
            b = domain.get(domName, [])
            if b == [] and a != []:
                self.domains[domName] = list(a)
            else:
                self.domains[domName] = list(b)

        # collect data
        self._generateGroundAtoms()
        if groundFormulas: self._createFormulaGroundings()
        if verbose:
            print "ground atoms: %d" % len(self.gndAtoms)
            print "ground formulas: %d" % len(self.gndFormulas)

        self._fitProbabilityConstraints(self.probreqs, self.probabilityFittingInferenceMethod, self.probabilityFittingThreshold, self.probabilityFittingMaxSteps, verbose=True)

    def minimizeGroupWeights(self):
        '''
            minimize the weights of formulas in groups by subtracting from each 
            formula weight the minimum weight in the group
            this results in weights relative to 0, therefore 
            this equivalence transformation can be thought of as a normalization
        '''
        wt = self._weights()
        for group in self.formulaGroups:
            if len(group) == 0:
                continue
            # find minimum absolute weight
            minWeight = wt[group[0]]
            for idxFormula in group:
                if abs(wt[idxFormula]) < abs(minWeight):
                    minWeight = wt[idxFormula]
            # shift all weights in the group
            for idxFormula in group:
                self.formulas[idxFormula].weight -= minWeight

    def setClosedWorldPred(self, *predicates):
        '''
        Sets the given predicate as closed-world (for inference)
        a predicate that is closed-world is assumed to be false for 
        any parameters not explicitly specified otherwise in the evidence.
        If predicateName is None, all predicates are set to open world.
        '''
        if len(predicates) == 1 and predicates[0] is None:
            self.closedWorldPreds = []
        else:
            for pred in predicates:
                if pred not in self.predicates:
                    raise Exception("Unknown predicate '%s'" % pred)
                self.closedWorldPreds.append(pred)

    def _weights(self):
        '''
        returns the weight vector of the MLN as a list
        '''
        return [f.weight for f in self.formulas]

    def learnWeights(self, databases, method=LearningMethods.BPLL, **params):
        '''
        Triggers the learning parameter learning process for a given set of databases.
        Returns a new MLN object with the learned parameters.
        - databases: list of Database objects or filenames
        '''
        log = logging.getLogger(self.__class__.__name__)
        self.verbose = params.get('verbose', False)
        # get a list of database objects
        if len(databases) == 0:
            log.exception('At least one database is needed for learning.')
        dbs = []
        for db in databases:
            if type(db) == str:
                db = readDBFromFile(self, db)
                if type(db) == list:
                    dbs.extend(db)
                else:
                    dbs.append(db)
            elif type(db) is list:
                dbs.extend(db)
            else:
                dbs.append(db)
        log.info('Got %s evidence databases for learning:' % len(dbs))
        log.debug(self.predicates)
        log.debug(self.domains)
        newMLN = self.materializeFormulaTemplates(dbs, self.verbose)
        
        log.debug('MLN predicates:')
        for p in newMLN.predicates:
            log.debug(p)
        log.debug('MLN domains:')
        for d in newMLN.domains.iteritems():
            log.debug(d)
        log.debug('MLN formulas:')
        for f in newMLN.iterFormulasPrintable():
            log.debug(f)
        if len(newMLN.formulas) == 0:
            raise Exception('No formulas in the materialized MLN.')
        # run learner
        if len(dbs) == 1:
            groundingMethod = eval('%s.groundingMethod' % method)
            log.info("grounding MRF using %s..." % groundingMethod) 
            mrf = newMLN.groundMRF(dbs[0], simplify=False, groundingMethod=groundingMethod, cwAssumption=True, **params)  # @UnusedVariable
            log.debug('Loading %s-Learner' % method)
            learner = eval("%s(newMLN, mrf, **params)" % method)
        else:
            learner = MultipleDatabaseLearner(newMLN, method, dbs, **params)
        log.info("learner: %s" % learner.getName())
        wt = learner.run(**params)

        # create the resulting MLN and set its weights
        learnedMLN = newMLN.duplicate()
        learnedMLN.setWeights(wt)

        # fit prior prob. constraints if any available
        if len(self.probreqs) > 0:
            fittingParams = {
                "fittingMethod": self.probabilityFittingInferenceMethod,
                "fittingSteps": self.probabilityFittingMaxSteps,
                "fittingThreshold": self.probabilityFittingThreshold
            }
            fittingParams.update(params)
            print "fitting with params ", fittingParams
            self._fitProbabilityConstraints(self.probreqs, **fittingParams)
        
        if self.verbose:
            learnedMLN.write(sys.stdout, color=True)
#             print "\n// formulas"
#             for formula in learnedMLN.formulas:
#                 print "%f  %s" % (float(eval(str(formula.weight))), strFormula(formula))
        return learnedMLN

    def setWeights(self, wt):
        if len(wt) != len(self.formulas):
            raise Exception("length of weight vector != number of formula templates")
        for i, f in enumerate(self.formulas):
            f.weight = float('%-10.6f' % float(eval(str(wt[i]))))

    def writeToFile(self, filename):
        '''
        Creates the file with the given filename and writes this MLN into it.
        '''
        f = open(filename, 'w+')
        self.write(f)   
        f.close()

    def write(self, f, mutexInDecls=True, color=False):
        '''
        Writes the MLN to the given stream
        - mutexInDecls:     whether to write the definitions for mutual 
        - exclusiveness:    directly to the predicate declaration (instead of extra constraints)
        - colorize:         whether or not output should be colorized.
        '''
        if 'learnwts_message' in dir(self):
            f.write("/*\n%s*/\n\n" % self.learnwts_message)
        f.write(colorize("// domain declarations\n", comment_color, color))
        for d in self.domDecls: 
            f.write("%s\n" % d)
        f.write('\n')
        f.write(colorize("\n// predicate declarations\n", comment_color, color))
        for predname, args in self.predicates.iteritems():
            excl = self.blocks.get(predname)
            if not mutexInDecls or excl is None:
                f.write("%s(%s)\n" % (colorize(predname, predicate_color, color), ", ".join(args)))
            else:
                f.write("%s(%s)\n" % (colorize(predname, predicate_color, color), 
                                      ", ".join(map(lambda x: "%s%s" % (x[0], {True:"!", False:""}[x[1]]), zip(args, excl)))))
        if not mutexInDecls:
            f.write(colorize("\n// mutual exclusiveness and exhaustiveness\n", comment_color))
            for predname, excl in self.blocks.iteritems():
                f.write("%s(" % (colorize(predname, predicate_color)))
                for i in range(len(excl)):
                    if i > 0: f.write(",")
                    f.write("a%d" % i)
                    if excl[i]: f.write("!")
                f.write(")\n")
        f.write(colorize("\n// formulas\n", comment_color, color))
        formulas = self.formulas if self.formulas is not None else self.formulas
        for formula in formulas:
            if formula.isHard:
                f.write("%s.\n" % strFormula(formula.cstr(color)))
            else:
                try:
                    w = colorize("%-10.6f", weight_color, color) % float(eval(str(formula.weight)))
                except:
                    w = colorize(str(formula.weight), weight_color, color)
                f.write("%s  %s\n" % (w, strFormula(formula.cstr(color))))

    def printFormulas(self):
        '''
        Nicely prints the formulas and their weights.
        '''
        for f in self.iterFormulasPrintable():
            print f
                
    def iterFormulasPrintable(self):
        '''
        Iterate over all formulas, yield nicely formatted strings.
        '''
        formulas = sorted(self.formulas)
        for f in formulas:
            if f.weight is None:
                yield '%s.' % strFormula(f)
            elif type(f.weight) is float:
                yield "%-10.6f\t%s" % (f.weight, strFormula(f))
            else:
                yield "%s\t%s" % (str(f.weight), strFormula(f))
        
    
    def getWeightedFormulas(self):
        return [(f.weight, f) for f in self.formulas]

    def getWeights(self):
        return [f.weight for f in self.formulas]


def readMLNFromString(text, searchPath='.', logic='FirstOrderLogic', grammar='PRACGrammar', verbose=False, mln=None):
    '''
    Reads an MLN from a stream providing a 'read' method.
    '''
    log = logging.getLogger(__name__)
    dirs = [os.path.abspath(searchPath)]
    formulatemplates = []
    text = str(text)
    if text == "": 
        raise MLNParsingError("No MLN content to construct model from was given; must specify either file/list of files or content string!")
    # replace some meta-directives in comments
    text = re.compile(r'//\s*<group>\s*$', re.MULTILINE).sub("#group", text)
    text = re.compile(r'//\s*</group>\s*$', re.MULTILINE).sub("#group.", text)
    # remove comments
    text = stripComments(text)
    log.info('Using %s syntax with %s semantics' % (grammar, logic))
    if mln is None:
        mln = MLN(logic, grammar)
    # read lines
    mln.hard_formulas = []
    if verbose: print "reading MLN..."
    templateIdx2GroupIdx = {}
    inGroup = False
    idxGroup = -1
    fixWeightOfNextFormula = False
    nextFormulaUnique = None
    uniqueFormulaExpansions = {}
    fixedWeightTemplateIndices = []
    lines = text.split("\n")
    iLine = 0
    while iLine < len(lines):
        line = lines[iLine]
        iLine += 1
        line = line.strip()
        try:
            if len(line) == 0: continue
            # meta directives
            if line == "#group":
                idxGroup += 1
                inGroup = True
                continue
            elif line == "#group.":
                inGroup = False
                continue
            elif line.startswith("#fixWeightFreq"):
                fixWeightOfNextFormula = True
                continue
            elif line.startswith("#include"):
                filename = line[len("#include "):].strip(whitespace + '"')
                # if the path is relative, look for the respective file 
                # relatively to all paths specified. Take the first file matching.
                if not os.path.isabs(filename):
                    includefilename = None
                    for d in dirs:
                        if os.path.exists(os.path.join(d, filename)):
                            includefilename = os.path.join(d, filename)
                            break
                    if includefilename is None:
                        log.error('No such file: "%s"' % filename)
                        raise Exception('File not found: %s' % filename)
                else:
                    includefilename = filename
                log.debug('Including file: "%s"' % includefilename)
                content = stripComments(file(includefilename, "r").read())
                lines = content.split("\n") + lines[iLine:]
                iLine = 0
                continue
            elif line.startswith('#unique'):
                try:
                    uniVars = re.search('#unique{(.+)}', line)
                    uniVars = uniVars.groups()[0]
                    log.debug(uniVars)
                    uniVars = map(str.strip, uniVars.split(','))
                    nextFormulaUnique = uniVars
                except:
                    raise MLNParsingError('Malformed #unique expression: "%s"' % line)
                continue
            elif line.startswith("#AdaptiveMLNDependency"): # declared as "#AdaptiveMLNDependency:pred:domain"; seems to be deprecated
                depPredicate, domain = line.split(":")[1:3]
                if hasattr(mln, 'AdaptiveDependencyMap'):
                    if depPredicate in mln.AdaptiveDependencyMap:
                        mln.AdaptiveDependencyMap[depPredicate].add(domain)
                    else:
                        mln.AdaptiveDependencyMap[depPredicate] = set([domain])
                else:
                    mln.AdaptiveDependencyMap = {depPredicate:set([domain])}
                continue
            # domain decl
            if '=' in line:
                # try normal domain definition
                parse = mln.logic.parseDomDecl(line)
                if parse is not None:
                    domName, constants = parse
                    domName = str(domName)
                    constants = map(str, constants)
                    log.info(domName)
                    log.info(constants)
                    if domName in mln.domains: 
                        log.warning("Domain redefinition: Domain '%s' is being updated with values %s." % (domName, str(constants)))
                    if domName not in mln.domains:
                        mln.domains[domName] = []
                    for value in constants:
                        if not value in mln.domains[domName]:
                            mln.domains[domName].append(value)
                    mln.domDecls.append(line)
                    continue
            # prior probability requirement
            if line.startswith("P("):
                m = re.match(r"P\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Prior probability constraint formatted incorrectly: %s" % line)
                mln.probreqs.append({"expr": strFormula(mln.logic.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # posterior probability requirement/soft evidence
            if line.startswith("R(") or line.startswith("SE("):
                m = re.match(r"(?:R|SE)\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Posterior probability constraint formatted incorrectly: %s" % line)
                mln.posteriorProbReqs.append({"expr": strFormula(mln.logic.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # variable definition
            if line.startswith("$"):
                m = re.match(r'(\$\w+)\s*=(.+)', line)
                if m is None:
                    raise MLNParsingError("Variable assigment malformed: %s" % line)
                mln.vars[m.group(1)] = "(%s)" % m.group(2).strip()
                continue                        
            # mutex constraint
            if re.search(r"[a-z_][-_'a-zA-Z0-9]*\!", line) != None:
                pred = mln.logic.parsePredDecl(line)
                mutex = []
                for param in pred[1]:
                    if param[-1] == '!':
                        mutex.append(True)
                    else:
                        mutex.append(False)
#                 mln.blocks[pred[0]] = mutex
                # if the corresponding predicate is not yet declared, take this to be the declaration
#                 if not pred[0] in mln.predicates:
                argTypes = map(lambda x: str(x).strip("!"), pred[1])
#                     mln.predicates[pred[0]] = argTypes
                mln.declarePredicate(str(pred[0]), argTypes, mutex)
                continue
            # predicate decl or formula with weight
            else:
                isHard = False
                isPredDecl = False
                if line[ -1] == '.': # hard (without explicit weight -> determine later)
                    isHard = True
                    formula = line[:-1]
                else: # with weight
                    # try predicate declaration
                    isPredDecl = True
                    try:
                        pred = mln.logic.parsePredDecl(line)
                    except Exception, e:
                        isPredDecl = False
                if isPredDecl:
                    predName = str(pred[0])
#                     if predName in mln.predicates:
#                         raise MLNParsingError("Predicate redefinition: '%s' already defined" % predName)
#                     mln.predicates[predName] = list(pred[1])
                    mln.declarePredicate(predName, map(str, pred[1]))
                    continue
                else:
                    # formula (template) with weight or terminated by '.'
                    if not isHard:
                        spacepos = line.find(' ')
                        weight = line[:spacepos]
                        formula = line[spacepos:].strip()
                    try:
                        formula = mln.logic.parseFormula(formula)
#                         log.warning(type(formula))
                        if not isHard:
                            formula.weight = weight
                        else:
                            formula.weight = None # not set until instantiation when other weights are known
                        formula.isHard = isHard
                        idxTemplate = len(formulatemplates)
                        formulatemplates.append(formula)
                        if inGroup:
                            templateIdx2GroupIdx[idxTemplate] = idxGroup
                        if fixWeightOfNextFormula == True:
                            fixWeightOfNextFormula = False
                            fixedWeightTemplateIndices.append(idxTemplate)
                        if nextFormulaUnique:
                            uniqueFormulaExpansions[formula] = nextFormulaUnique
                            nextFormulaUnique = None
                    except ParseException, e:
                        raise MLNParsingError("Error parsing formula '%s'\n" % formula)
        except MLNParsingError:
            sys.stderr.write("Error processing line '%s'\n" % line)
            cls, e, tb = sys.exc_info()
            traceback.print_tb(tb)
            raise MLNParsingError(e.message)

    # augment domains with constants appearing in formula templates
    for f in formulatemplates:
        constants = {}
        f.getVariables(mln, None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: mln.addConstant(domain, c)
    
    # save data on formula templates for materialization
    mln.uniqueFormulaExpansions = uniqueFormulaExpansions
    mln.formulas = formulatemplates
    mln.templateIdx2GroupIdx = templateIdx2GroupIdx
    mln.fixedWeightTemplateIndices = fixedWeightTemplateIndices
    return mln

def readMLNFromFile(filename_or_list, logic='FirstOrderLogic', grammar='PRACGrammar', verbose=False):
    '''
    Reads an MLN object from a file or a set of files.
    '''
    # read MLN file
    log = logging.getLogger('parsing')
    text = ""
    if filename_or_list is not None:
        if not type(filename_or_list) == list:
            filename_or_list = [filename_or_list]
        for filename in filename_or_list:
            #print filename
            f = file(filename)
            text += f.read()
            f.close()
    dirs = [os.path.dirname(fn) for fn in filename_or_list]
    formulatemplates = []
    if text == "": 
        raise MLNParsingError("No MLN content to construct model from was given; must specify either file/list of files or content string!")
    # replace some meta-directives in comments
    text = re.compile(r'//\s*<group>\s*$', re.MULTILINE).sub("#group", text)
    text = re.compile(r'//\s*</group>\s*$', re.MULTILINE).sub("#group.", text)
    # remove comments
    text = stripComments(text)
    log.info('Using %s syntax with %s semantics' % (grammar, logic))
    mln = MLN(logic, grammar)
    # read lines
    mln.hard_formulas = []
    if verbose: print "reading MLN..."
    templateIdx2GroupIdx = {}
    inGroup = False
    idxGroup = -1
    fixWeightOfNextFormula = False
    nextFormulaUnique = None
    uniqueFormulaExpansions = {}
    fixedWeightTemplateIndices = []
    lines = text.split("\n")
    iLine = 0
    while iLine < len(lines):
        line = lines[iLine]
        iLine += 1
        line = line.strip()
        try:
            if len(line) == 0: continue
            # meta directives
            if line == "#group":
                idxGroup += 1
                inGroup = True
                continue
            elif line == "#group.":
                inGroup = False
                continue
            elif line.startswith("#fixWeightFreq"):
                fixWeightOfNextFormula = True
                continue
            elif line.startswith("#include"):
                filename = line[len("#include "):].strip(whitespace + '"')
                # if the path is relative, look for the respective file 
                # relatively to all paths specified. Take the first file matching.
                if not os.path.isabs(filename):
                    includefilename = None
                    for d in dirs:
                        if os.path.exists(os.path.join(d, filename)):
                            includefilename = os.path.join(d, filename)
                            break
                    if includefilename is None:
                        log.error('No such file: "%s"' % filename)
                        raise Exception('File not found: ' % filename)
                else:
                    includefilename = filename
                log.debug('Including file: "%s"' % includefilename)
                content = stripComments(file(includefilename, "r").read())
                lines = content.split("\n") + lines[iLine:]
                iLine = 0
                continue
            elif line.startswith('#unique'):
                try:
                    uniVars = re.search('#unique{(.+)}', line)
                    uniVars = uniVars.groups()[0]
                    log.debug(uniVars)
                    uniVars = map(str.strip, uniVars.split(','))
                    nextFormulaUnique = uniVars
                except:
                    raise MLNParsingError('Malformed #unique expression: "%s"' % line)
                continue
            elif line.startswith("#AdaptiveMLNDependency"): # declared as "#AdaptiveMLNDependency:pred:domain"; seems to be deprecated
                depPredicate, domain = line.split(":")[1:3]
                if hasattr(mln, 'AdaptiveDependencyMap'):
                    if depPredicate in mln.AdaptiveDependencyMap:
                        mln.AdaptiveDependencyMap[depPredicate].add(domain)
                    else:
                        mln.AdaptiveDependencyMap[depPredicate] = set([domain])
                else:
                    mln.AdaptiveDependencyMap = {depPredicate:set([domain])}
                continue
            # domain decl
            if '=' in line:
                # try normal domain definition
                parse = mln.logic.parseDomDecl(line)
                if parse is not None:
                    domName, constants = parse
                    domName = str(domName)
                    constants = map(str, constants)
                    if domName in mln.domains: 
                        log.warning("Domain redefinition: Domain '%s' is being updated with values %s." % (domName, str(constants)))
                    if domName not in mln.domains:
                        mln.domains[domName] = []
                    for value in constants:
                        if not value in mln.domains[domName]:
                            mln.domains[domName].append(value)
                    mln.domDecls.append(line)
                    continue
            # prior probability requirement
            if line.startswith("P("):
                m = re.match(r"P\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Prior probability constraint formatted incorrectly: %s" % line)
                mln.probreqs.append({"expr": strFormula(mln.logic.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # posterior probability requirement/soft evidence
            if line.startswith("R(") or line.startswith("SE("):
                m = re.match(r"(?:R|SE)\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Posterior probability constraint formatted incorrectly: %s" % line)
                mln.posteriorProbReqs.append({"expr": strFormula(mln.logic.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # variable definition
            if line.startswith("$"):
                m = re.match(r'(\$\w+)\s*=(.+)', line)
                if m is None:
                    raise MLNParsingError("Variable assigment malformed: %s" % line)
                mln.vars[m.group(1)] = "(%s)" % m.group(2).strip()
                continue                        
            # mutex constraint
            if re.search(r"[a-z_][-_'a-zA-Z0-9]*\!", line) != None:
                pred = mln.logic.parsePredDecl(line)
                mutex = []
                for param in pred[1]:
                    if param[-1] == '!':
                        mutex.append(True)
                    else:
                        mutex.append(False)
                mln.blocks[pred[0]] = mutex
                # if the corresponding predicate is not yet declared, take this to be the declaration
                if not pred[0] in mln.predicates:
                    argTypes = map(lambda x: str(x).strip("!"), pred[1])
                    mln.predicates[str(pred[0])] = argTypes
                continue
            # predicate decl or formula with weight
            else:
                isHard = False
                isPredDecl = False
                if line[ -1] == '.': # hard (without explicit weight -> determine later)
                    isHard = True
                    formula = line[:-1]
                else: # with weight
                    # try predicate declaration
                    isPredDecl = True
                    try:
                        pred = mln.logic.parsePredDecl(line)
                    except Exception, e:
                        isPredDecl = False
                if isPredDecl:
                    predName = str(pred[0])
                    if predName in mln.predicates:
                        raise MLNParsingError("Predicate redefinition: '%s' already defined" % predName)
                    pred[1] = map(str, pred[1])
                    mln.predicates[predName] = list(pred[1])
                    continue
                else:
                    # formula (template) with weight or terminated by '.'
                    if not isHard:
                        spacepos = line.find(' ')
                        weight = line[:spacepos]
                        formula = line[spacepos:].strip()
                    try:
                        formula = mln.logic.parseFormula(formula)
#                         log.warning(type(formula))
                        if not isHard:
                            formula.weight = weight
                        else:
                            formula.weight = None # not set until instantiation when other weights are known
                        formula.isHard = isHard
                        idxTemplate = len(formulatemplates)
                        formulatemplates.append(formula)
                        if inGroup:
                            templateIdx2GroupIdx[idxTemplate] = idxGroup
                        if fixWeightOfNextFormula == True:
                            fixWeightOfNextFormula = False
                            fixedWeightTemplateIndices.append(idxTemplate)
                        if nextFormulaUnique:
                            uniqueFormulaExpansions[formula] = nextFormulaUnique
                            nextFormulaUnique = None
                    except ParseException, e:
                        raise MLNParsingError("Error parsing formula '%s'\n" % formula)
        except MLNParsingError:
            sys.stderr.write("Error processing line '%s'\n" % line)
            cls, e, tb = sys.exc_info()
            traceback.print_tb(tb)
            raise MLNParsingError(e.message)

    # augment domains with constants appearing in formula templates
    for f in formulatemplates:
        constants = {}
        f.getVariables(mln, None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: mln.addConstant(domain, c)
    
    # save data on formula templates for materialization
    mln.uniqueFormulaExpansions = uniqueFormulaExpansions
    mln.formulas = formulatemplates
    mln.templateIdx2GroupIdx = templateIdx2GroupIdx
    mln.fixedWeightTemplateIndices = fixedWeightTemplateIndices
    return mln



    