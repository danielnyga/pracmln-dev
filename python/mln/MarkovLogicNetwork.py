# -*- coding: iso-8859-1 -*-
#
# Markov Logic Networks
#
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
from mln.database import Database, readDBFromFile
import logic
from logic.grammar import predDecl, parseFormula
from mln.inference.bnbinference import BnBInference
import copy
from utils import dict_union

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

DEBUG = False

import sys
import os
import random
import time
import traceback

sys.setrecursionlimit(10000)

import platform
if platform.architecture()[0] == '32bit':
    try:
        if not DEBUG:
            import psyco # Don't use Psyco when debugging!
            psyco.full()
    except:
        sys.stderr.write("Note: Psyco (http://psyco.sourceforge.net) was not loaded. On 32bit systems, it is recommended to install it for improved performance.\n")

from pyparsing import ParseException
from inference import *
from util import *
from methods import *
import learning
from grounding import *

POSSWORLDS_BLOCKING = True

# -- Markov logic network

class MLN(object):
    '''
    represents a Markov logic network and/or a ground Markov network

    members:
        blocks:
            dict: predicate name -> list of booleans that indicate which arguments of the pred are functionally determined by the others
            (one boolean per argument, True = is functionally determined)
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

    def __init__(self, defaultInferenceMethod=InferenceMethods.MCSAT, parameterType='weights', verbose=False):
        '''
        Constructs an empty MLN object. For reading an MLN object 
        from an .mln file, see readMLNFromFile (below).
        '''
        self.predDecls = {}
        self.formulaTemplates = []
        self.staticDomains = {}
        self.predicates = None
        self.domains = None
        self.formulas = None

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
        self.verbose = verbose

    def duplicate(self):
        '''
        Returns a deep copy of this MLN, which is not yet materialized.
        '''
        mln = MLN()
        mln.predDecls = copy.deepcopy(self.predDecls)
        mln.staticDomains = copy.deepcopy(self.predDecls)
        mln.formulaTemplates = list(self.formulaTemplates)
        mln.blocks = copy.deepcopy(self.blocks)
        mln.domDecls = list(self.domDecls)
        mln.closedWorldPreds = list(self.closedWorldPreds)
        mln.parameterType = self.parameterType
        mln.learnWtsMode = self.learnWtsMode
        return mln

    def declarePredicate(self, name, domains, functional=None):
        '''
        Adds a predicate declaration to the MLN:
        - name:        name of the predicate (string)
        - domains:     list of domain names of arguments
        - functional:  indices of args which are functional (optional)
        '''
        if name in self.predDecls:
            raise Exception('Predicate "%s" has already been declared' % name)
        assert type(domains) == list
        self.predDecls[name] = domains
        if functional is not None:
            func = [(i in functional) for i, _ in enumerate(domains)]
            self.blocks[name] = func
            
    def loadPRACDatabases(self, dbPath):
        '''
        Loads and returns all databases (*.db files) that are located in 
        the given directory and returns the corresponding Database objects.
        - dbPath:     the directory path to look for .db files
        '''
        dbs = []
#        senses = set()
        for dirname, dirnames, filenames in os.walk(dbPath): #@UnusedVariable
            for f in filenames:
                if not f.endswith('.db'):
                    continue
                p = os.path.join(dirname, f)
                print "  reading database %s" % p
                db = Database(self, p)
#                senses.update(db.domains['sense'])
                dbs.append(db)
        print "  %d databases read" % len(dbs)
        return dbs
    
    def addFormula(self, formula, weight=0, hard=False, fixWeight=False):
        '''
        Add a formula to this MLN. The respective domains of constants
        are updated, if necessary.
        '''
        self._addFormula(formula, self.formulas, weight, hard, fixWeight)
    
    def addFormulaTemplate(self, formula, weight=0, hard=False, fixWeight=False):
        '''
        Add a formula template (i.e. formulas with '+' operators) to the MLN.
        Domains are updated, if necessary.
        '''
        self._addFormula(formula, self.formulaTemplates, weight, hard, fixWeight)
        
    def _addFormula(self, formula, formulaSet, weight=0, hard=False, fixWeight=False):
        '''
        Adds the given formula to the MLN and extends the respective domains, if necessary.
        - formula:    a FOL.Formula object or a string
        - weight:     weight of the formula
        - hard:       determines if the formula is hard
        - fixWeight:  determines if the weight of the formula is fixed
        '''
        if type(formula) is str:
            formula = parseFormula(formula)
        formula.weight = weight
        formula.isHard = hard
        idxTemplate = len(formulaSet)
        if fixWeight:
            self.fixedWeightTemplateIndices.append(idxTemplate)
        formulaSet.append(formula)
        # extend domains
        constants = {}
        formula.getVariables(self, None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: 
                self.addConstant(domain, c)

    def materializeFormulaTemplates(self, dbs, verbose=False):
        '''
        Expand all formula templates.
        - dbs: list of Database objects
        '''
        print "materializing formula templates..."
        self.predicates = {}
        self.domains = {}
        self.formulas = []
        
        # obtain full domain with all objects 
        fullDomain = mergeDomains(self.staticDomains, *[db.domains for db in dbs])
        # expand formula templates
        self.domains = copy.deepcopy(self.staticDomains)
        
        # collect the admissible formula templates
        templates = []
        emptyDomains = set()
        for ft in self.formulaTemplates:
            domNames = ft.getVariables(self).values()
            discardFT = False
            for domName in domNames:
                if not domName in fullDomain:
                    emptyDomains.add(domName)
                    print 'WARNING: Discarding formula %s, since it cannot be grounded (domain %s empty).' % (strFormula(ft), domName)
                    discardFT = True
                    break
            if discardFT: continue
            templates.append(ft)
        
        # collect the admissible predicates
        for pred, domains in self.predDecls.iteritems():
            if any(map(lambda d: not d in fullDomain, self.predDecls[pred])):
                print 'WARNING: Discarding predicate %s, since it cannot be grounded.' % (pred)
                continue
            self.predicates[pred] = domains
        
        # permanently transfer domains of variables that were expanded from templates
        for ft in templates:
            domNames = ft._getTemplateVariables(self).values()
            for domName in domNames:
                self.domains[domName] = fullDomain[domName]
        self._materializeFormulaTemplates(templates)
#         self.printFormulas()
#         print len(self.formulas), 'formulas'

    def _materializeFormulaTemplates(self, templates, verbose=False):

        templateIdx2GroupIdx = self.templateIdx2GroupIdx
        fixedWeightTemplateIndices = self.fixedWeightTemplateIndices

        # materialize formula templates
        if verbose: print "materializing formula templates..."
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
        if domainName not in self.staticDomains: self.staticDomains[domainName] = []
        dom = self.staticDomains[domainName]
        if constant not in dom: dom.append(constant)

    def _substVar(self, matchobj):
        varName = matchobj.group(0)
        if varName not in self.vars:
            raise Exception("Unknown variable '%s'" % varName)
        return self.vars[varName]

    def groundMRF(self, db, simplify=False, method='DefaultGroundingFactory', cwAssumption=False, **params):
        '''
        Creates and returns a ground Markov Random Field for the given database
        - db: database filename (string) or Database object
        '''
        mrf = MRF(self, db, method, **params)
        # apply closed world assumption
        if cwAssumption:
            mrf.evidence = map(lambda x: False if x is None else x, mrf.evidence)
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
            minimize the weights of formulas in groups by subtracting from each formula weight the minimum weight in the group
            this results in weights relative to 0, therefore this equivalence transformation can be thought of as a normalization
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

    def setClosedWorldPred(self, predicateName):
        '''
        Sets the given predicate as closed-world (for inference)
        a predicate that is closed-world is assumed to be false for 
        any parameters not explicitly specified otherwise in the evidence.
        If predicateName is None, all predicates are set to open world.
        '''
        if predicateName is None:
            self.closedWorldPreds = []
        else:
            if predicateName not in self.predDecls:
                raise Exception("Unknown predicate '%s'" % predicateName)
            self.closedWorldPreds.append(predicateName)

    def _weights(self):
        '''
        returns the weight vector of the MLN as a list
        '''
        return [f.weight for f in self.formulas]

    def learnWeights(self, databases, method=ParameterLearningMeasures.BPLL, **params):
        '''
        databases: list of Database objects or filenames
        '''
        # get a list of database objects
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
        
#         if self.formulas is None:
        self.materializeFormulaTemplates(dbs, self.verbose)
            
        # run learner
        if len(dbs) == 1:
            groundingMethod = eval('learning.%s.groundingMethod' % method)
            print "grounding MRF using %s..." % groundingMethod 
            mrf = self.groundMRF(dbs[0], method=groundingMethod, cwAssumption=True, **params)
            learner = eval("learning.%s(self, mrf, **params)" % method)
        else:
            learner = learning.MultipleDatabaseLearner(self, method, dbs, **params)
        print "learner: %s" % learner.getName()
        wt = learner.run(**params)

        # create the resulting MLN and set its weights
        learnedMLN = self.duplicate()
        learnedMLN.formulaTemplates = list(self.formulas)
        learnedMLN.staticDomains = copy.deepcopy(self.domains)
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
            print "\n// formulas"
            for formula in learnedMLN.formulaTemplates:
                print "%f  %s" % (float(eval(str(formula.weight))), strFormula(formula))
        return learnedMLN

    def setWeights(self, wt):
        if len(wt) != len(self.formulaTemplates):
            raise Exception("length of weight vector != number of formula templates")
        for i, f in enumerate(self.formulaTemplates):
            f.weight = float('%-10.6f' % float(eval(str(wt[i]))))

    def write(self, f, mutexInDecls=True):
        '''
            writes the MLN to the given file object
                mutexInDecls: whether to write the definitions for mutual exclusiveness directly to the predicate declaration (instead of extra constraints)
        '''
        if 'learnwts_message' in dir(self):
            f.write("/*\n%s*/\n\n" % self.learnwts_message)
        f.write("// domain declarations\n")
        for d in self.domDecls: f.write("%s\n" % d)
        f.write("\n// predicate declarations\n")
        for predname, args in self.predDecls.iteritems():
            excl = self.blocks.get(predname)
            if not mutexInDecls or excl is None:
                f.write("%s(%s)\n" % (predname, ", ".join(args)))
            else:
                f.write("%s(%s)\n" % (predname, ", ".join(map(lambda x: "%s%s" % (x[0], {True:"!", False:""}[x[1]]), zip(args, excl)))))
        if not mutexInDecls:
            f.write("\n// mutual exclusiveness and exhaustiveness\n")
            for predname, excl in self.blocks.iteritems():
                f.write("%s(" % (predname))
                for i in range(len(excl)):
                    if i > 0: f.write(",")
                    f.write("a%d" % i)
                    if excl[i]: f.write("!")
                f.write(")\n")
        f.write("\n// formulas\n")
        formulas = self.formulas if self.formulas is not None else self.formulaTemplates
        for formula in formulas:
            if formula.isHard:
                f.write("%s.\n" % strFormula(formula))
            else:
                try:
                    weight = "%-10.6f" % float(eval(str(formula.weight)))
                except:
                    weight = str(formula.weight)
                f.write("%s  %s\n" % (weight, strFormula(formula)))

    def printFormulas(self):
        '''
        Nicely prints the formulas and their weights.
        '''
        if self.formulas is None:
            formulas = self.formulaTemplates
        else:
            formulas = self.formulas
        for f in formulas:
            if f.weight is None:
                print '%s.' % strFormula(f)
            elif type(f.weight) is float:
                print "%-10.6f\t%s" % (f.weight, strFormula(f))
            else:
                print "%s\t%s" % (str(f.weight), strFormula(f))
    
    def getWeightedFormulas(self):
        return [(f.weight, f) for f in self.formulas]

    def getWeights(self):
        return [f.weight for f in self.formulas]



class MRF(object):
    '''
    Represents a ground Markov Random Field

    members:
        gndAtoms:
            maps a string representation of a ground atom to a fol.GroundAtom object
        gndAtomsByIdx:
            dict: ground atom index -> fol.GroundAtom object
        evidence:
            list: ground atom index -> truth values
        gndBlocks:
            dict: block name -> list of ground atom indices
        gndBlockLookup:
            dict: ground atom index -> block name
        gndAtomOccurrencesInGFs
            dict: ground atom index -> ground formula
        gndFormulas:
            list of grounded formula objects
        pllBlocks:
            list of *all* the ground blocks, including trivial blocks consisting of a single ground atom
            each element is a tuple (ground atom index, list of ground atom indices) where one element is always None
    '''


    __init__params = {'verbose': False, 
                  'simplify': False, 
                  'initWeights': False}
    
    def __init__(self, mln, db, groundingMethod='DefaultGroundingFactory', **params):
        '''
        - db:        database filename (.db) or a Database object
        - params:    dict of keyword parameters. Valid values are:
            - simplify: (True/False) determines if the formulas should be simplified
                        during the grounding process.
            - verbose:  (True/False) Verbose mode on/off
            - groundingMethod: (string) name of the grounding factory to be used (default: DefaultGroundingFactory)
            - initWeights: (True/False) Switch on/off heuristics for initial weight determination (only for learning!)
        '''
        self.params = dict_union(MRF.__init__params, params)
        verbose = self.params['verbose']
        self.mln = mln
        self.evidence = None
        self.evidenceBackup = {}
        self.softEvidence = list(mln.posteriorProbReqs) # constraints on posterior 
                                                        # probabilities are nothing but 
                                                        #soft evidence and can be handled in exactly the same way
        self.simplify = self.params['simplify']
        
        # ground members
        self.gndAtoms = {}
        self.gndBlockLookup = {}
        self.gndBlocks = {}
        self.gndAtomsByIdx = {}
        self.gndFormulas = []
        self.gndAtomOccurrencesInGFs = []
        
        if type(db) == str:
            db = readDBFromFile(self.mln, db)
        elif isinstance(db, Database):
            pass
        else:
            raise Exception("Not a valid database argument (type %s)" % (str(type(db))))
        # materialize MLN formulas
        if self.mln.formulas is None:
            self.mln.materializeFormulaTemplates([db],verbose)
        self.formulas = list(mln.formulas) # copy the list of formulas, because we may change or extend it
        # materialize formula weights
        self._materializeFormulaWeights(verbose)

        self.closedWorldPreds = list(mln.closedWorldPreds)
        self.probreqs = list(mln.probreqs)
        self.posteriorProbReqs = list(mln.posteriorProbReqs)
        self.predicates = copy.deepcopy(mln.predicates)
        self.predDecls = copy.deepcopy(mln.predDecls)
        self.templateIdx2GroupIdx = mln.templateIdx2GroupIdx

        # get combined domain
        self.domains = mergeDomains(mln.domains, db.domains)

        # grounding
        if verbose: print 'Loading %s...' % groundingMethod
        groundingMethod = eval('%s(self, db, **self.params)' % groundingMethod)
        self.groundingMethod = groundingMethod
        groundingMethod.groundMRF()
        assert len(self.gndAtoms) == len(self.evidence)

    def getHardFormulas(self):
        '''
        Returns a list of all hard formulas in this MRF.
        '''
        return [f for f in self.formulas if f.weight is None]

    def _getPredGroundings(self, predName):
        '''
        Gets the names of all ground atoms of the given predicate.
        '''
        # get the string represenation of the first grounding of the predicate
        domNames = self.predicates[predName]
        params = []
        for domName in domNames:
            params.append(self.domains[domName][0])
        gndAtom = "%s(%s)" % (predName, ",".join(params))
        # get all subsequent groundings (by index) until the predicate name changes
        groundings = []
        idx = self.gndAtoms[gndAtom].idx
        while True:
            groundings.append(gndAtom)
            idx += 1
            if idx >= len(self.gndAtoms):
                break
            gndAtom = str(self.gndAtomsByIdx[idx])
            if parsePredicate(gndAtom)[0] != predName:
                break
        return groundings

    def _getPredGroundingsAsIndices(self, predName):
        '''
            get a list of all the indices of all groundings of the given predicate
        '''
        # get the index of the first grounding of the predicate and the number of groundings
        domNames = self.predicates[predName]
        params = []
        numGroundings = 1
        for domName in domNames:
            params.append(self.domains[domName][0])
            numGroundings *= len(self.domains[domName])
        gndAtom = "%s(%s)" % (predName, ",".join(params))
        idxFirst = self.gndAtoms[gndAtom].idx
        return range(idxFirst, idxFirst + numGroundings)

    def _materializeFormulaWeights(self, verbose=False):
        '''
        materialize all formula weights.
        '''
        max_weight = 0
        for f in self.formulas:
            if f.weight is not None:
                w = str(f.weight)
                while "$" in w:
                    try:
                        w, numReplacements = re.subn(r'\$\w+', self._substVar, w)
                    except:
                        sys.stderr.write("Error substituting variable references in '%s'\n" % w)
                        raise
                    if numReplacements == 0:
                        raise Exception("Undefined variable(s) referenced in '%s'" % w)
                w = re.sub(r'domSize\((.*?)\)', r'self.domSize("\1")', w)
                try:
                    f.weight = float(eval(w))
                except:
                    sys.stderr.write("Evaluation error while trying to compute '%s'\n" % w)
                    raise
                max_weight = max(abs(f.weight), max_weight)

        # set weights of hard formulas
        hard_weight = 20 + max_weight
        self.hard_weight = hard_weight
        hard_formulas = self.getHardFormulas()
        if verbose: print "setting %d hard weights to %f" % (len(hard_formulas), hard_weight)
        for f in hard_formulas:
            if verbose: print "  ", strFormula(f)
            f.weight = hard_weight

    def addGroundAtom(self, gndLit):
        '''
        Adds a ground atom to the set (actually it's a dict) of ground atoms.
        gndLit: a fol.GroundAtom object
        '''
        if str(gndLit) in self.gndAtoms:
            return

        atomIdx = len(self.gndAtoms)
        gndLit.idx = atomIdx
        self.gndAtomsByIdx[gndLit.idx] = gndLit
        self.gndAtoms[str(gndLit)] = gndLit
        self.gndAtomOccurrencesInGFs.append([])
        
        # check if atom is in block and update the lookup
        mutex = self.mln.blocks.get(gndLit.predName)
        if mutex != None:
            blockName = "%s_" % gndLit.predName
            for i, v in enumerate(mutex):
                if v == False:
                    blockName += gndLit.params[i]
            if not blockName in self.gndBlocks:
                self.gndBlocks[blockName] = []
            self.gndBlocks[blockName].append(gndLit.idx)
            self.gndBlockLookup[gndLit.idx] = blockName

    def _addGroundFormula(self, gndFormula, idxFormula, idxGndAtoms = None):
        '''
        Adds a ground formula to the MRF.

        - idxGndAtoms: indices of the ground atoms that are referenced by the 
        - formula (precomputed); If not given (None), will be determined automatically
        '''
        gndFormula.idxFormula = idxFormula
        self.gndFormulas.append(gndFormula)
        # update ground atom references
        if idxGndAtoms is None:
            idxGndAtoms = gndFormula.idxGroundAtoms()
        for idxGA in idxGndAtoms:
            self.gndAtomOccurrencesInGFs[idxGA].append(gndFormula)

    def removeGroundFormulaData(self):
        '''
        remove data on ground formulas to save space (e.g. because the necessary statistics were already collected and the actual formulas
        are no longer needed)
        '''
        del self.gndFormulas
        del self.gndAtomOccurrencesInGFs
#         del self.mln.gndFormulas
#         del self.mln.gndAtomOccurrencesInGFs
        if hasattr(self, "blockRelevantGFs"):
            del self.blockRelevantGFs

    def _addFormula(self, formula, weight):
        idxFormula = len(self.formulas)
        formula.weight = weight
        self.formulas.append(formula)
        return idxFormula

    def _setEvidence(self, idxGndAtom, value):
        self.evidence[idxGndAtom] = value

    def _setTemporaryEvidence(self, idxGndAtom, value):
        self.evidenceBackup[idxGndAtom] = self._getEvidence(idxGndAtom, closedWorld=False)
        self._setEvidence(idxGndAtom, value)

    def _getEvidence(self, idxGndAtom, closedWorld=True):
        '''
            gets the evidence truth value for the given ground atom or None if no evidence was given
            if closedWorld is True, False instead of None is returned
        '''
        v = self.evidence[idxGndAtom]
        if closedWorld and v == None:
            return False
        return v

    def _clearEvidence(self):
        '''
        Erases the evidence in this MRF.
        '''
        self.evidence = [None] * len(self.gndAtoms)#dict([(i, None) for i in range(len(self.gndAtoms))])

    def getEvidenceDatabase(self):
        '''
        returns, from the current evidence list, a dictionary that maps ground atom names to truth values
        '''
        d = {}
        for idxGA, tv in enumerate(self.evidence):
            if tv != None:
                d[str(self.gndAtomsByIdx[idxGA])] = tv
        return d

    def printEvidence(self):
        for idxGA, value in enumerate(self.evidence):
            print "%s = %s" % (str(self.gndAtomsByIdx[idxGA]), str(value))

    def _getEvidenceTruthDegreeCW(self, gndAtom, worldValues):
        '''
            gets (soft or hard) evidence as a degree of belief from 0 to 1, making the closed world assumption,
            soft evidence has precedence over hard evidence
        '''
        se = self._getSoftEvidence(gndAtom)
        if se is not None:
            if (True == worldValues[gndAtom.idx] or None == worldValues[gndAtom.idx]):
                return se 
            else: 
                return 1.0 - se # TODO allSoft currently unsupported
        if worldValues[gndAtom.idx]:
            return 1.0
        else: return 0.0

    def _getEvidenceDegree(self, gndAtom):
        '''
            gets (soft or hard) evidence as a degree of belief from 0 to 1 or None if no evidence is given,
            soft evidence takes precedence over hard evidence
        '''
        se = self._getSoftEvidence(gndAtom)
        if se is not None:
            return se
        he = self._getEvidence(gndAtom.idx, False)
        if he is None:
            return None
        if he == True:
            return 1.0
        else: return 0.0


    def _getSoftEvidence(self, gndAtom):
        '''
            gets the soft evidence value (probability) for a given ground atom (or complex formula)
            returns None if there is no such value
        '''
        s = strFormula(gndAtom)
        for se in self.softEvidence: # TODO optimize
            if se["expr"] == s:
                #print "worldValues[gndAtom.idx]", worldValues[gndAtom.idx]
                return se["p"]
        return None

    def _setSoftEvidence(self, gndAtom, value):
        s = strFormula(gndAtom)
        for se in self.softEvidence:
            if se["expr"] == s:
                se["p"] = value
                return

    def getTruthDegreeGivenSoftEvidence(self, gf, worldValues):
        cnf = gf.toCNF()
        prod = 1.0
        if isinstance(cnf, fol.Conjunction):
            for disj in cnf.children:
                prod *= self._noisyOr(worldValues, disj)
        else:
            prod *= self._noisyOr(worldValues, cnf)
        return prod

    def _noisyOr(self, mln, worldValues, disj):
        if isinstance(disj, fol.GroundLit):
            lits = [disj]
        elif isinstance(disj, fol.TrueFalse):
            if disj.isTrue(worldValues):
                return 1.0
            else: return 0.0
        else:
            lits = disj.children
        prod = 1.0
        for lit in lits:
            p = mln._getEvidenceTruthDegreeCW(lit.gndAtom, worldValues)
            if not lit.negated:
                factor = p 
            else:
                factor = 1.0 - p
            prod *= 1.0 - factor
        return 1.0 - prod

    def _removeTemporaryEvidence(self):
        for idx, value in self.evidenceBackup.iteritems():
            self._setEvidence(idx, value)
        self.evidenceBackup.clear()

    def _isTrueGndFormulaGivenEvidence(self, gf):
        return gf.isTrue(self.evidence)

    def setEvidence(self, evidence, clear=True):
        '''
        Sets the evidence, which is to be given as a dictionary that maps ground atom strings to their truth values.
        Any previous evidence is cleared.
        The closed-world assumption is applied to any predicates for which it was declared.
        '''
        if clear is True:
            self._clearEvidence()
        for gndAtom, value in evidence.iteritems():
            idx = self.gndAtoms[gndAtom].idx
            self._setEvidence(idx, value)
            # If the value is true, set evidence for other vars in block (if any)
            if value == True and idx in self.gndBlockLookup:
                block = self.gndBlocks[self.gndBlockLookup[idx]]
                for i in block:
                    if i != idx:
                        self._setEvidence(i, False)
        # handle closed-world predicates: Set all their instances that aren't yet known to false
        for pred in self.closedWorldPreds:
            if not pred in self.predicates: continue
            for idxGA in self._getPredGroundingsAsIndices(pred):
                if self._getEvidence(idxGA, False) == None:
                    self._setEvidence(idxGA, False)

    def _getPllBlocks(self):
        '''
        creates an array self.pllBlocks that contains tuples (idxGA, block);
        one of the two tuple items is always None depending on whether the ground atom is in a block or not; 
        '''
        if hasattr(self, "pllBlocks"):
            return
        handledBlockNames = []
        self.pllBlocks = []
        for idxGA in range(len(self.gndAtoms)):
            if idxGA in self.gndBlockLookup:
                blockName = self.gndBlockLookup[idxGA]
                if blockName in handledBlockNames:
                    continue
                self.pllBlocks.append((None, self.gndBlocks[blockName]))
                handledBlockNames.append(blockName)
            else:
                self.pllBlocks.append((idxGA, None))

    def _getBlockRelevantGroundFormulas(self):
        '''
        computes the set of relevant ground formulas for each block
        '''
        mln = self
        self.blockRelevantGFs = [set() for _ in range(len(mln.pllBlocks))]
        for idxBlock, (idxGA, block) in enumerate(mln.pllBlocks):
            if block != None:
                for idxGA in block:
                    for gf in self.gndAtomOccurrencesInGFs[idxGA]:
                        self.blockRelevantGFs[idxBlock].add(gf)
            else:
                self.blockRelevantGFs[idxBlock] = self.gndAtomOccurrencesInGFs[idxGA]

    def _getBlockTrueone(self, block):
        idxGATrueone = -1
        for i in block:
            if self._getEvidence(i):
                if idxGATrueone != -1: 
                    raise Exception("More than one true ground atom in block %s!" % self._strBlock(block))
                idxGATrueone = i
                break
        if idxGATrueone == -1: raise Exception("No true gnd atom in block %s!" % self._strBlock(block))
        return idxGATrueone

    def _getBlockName(self, idxGA):
        return self.gndBlockLookup[idxGA]

    def _strBlock(self, block):
        return "{%s}" % (",".join(map(lambda x: str(self.gndAtomsByIdx[x]), block)))
    
    def _strBlockVar(self, varIdx):
        (idxGA, block) = self.pllBlocks[varIdx]
        if block is None:
            return str(self.gndAtomsByIdx[idxGA])
        else:
            return self._strBlock(block)

    def _getBlockExpsums(self, block, wt, world_values, idxGATrueone=None, relevantGroundFormulas=None):
        # if the true gnd atom in the block is not known (or there isn't one perhaps), set the first one to true by default and restore values later
        mustRestoreValues = False
        if idxGATrueone == None:
            mustRestoreValues = True
            backupValues = [world_values[block[0]]]
            world_values[block[0]] = True
            for idxGA in block[1:]:
                backupValues.append(world_values[idxGA])
                world_values[idxGA] = False
            idxGATrueone = block[0]
        # init sum of weights for each possible assignment of block
        # sums[i] = sum of weights for assignment where the block[i] is set to true
        sums = [0 for i in range(len(block))] 
        # process all (relevant) ground formulas
        checkRelevance = False
        if relevantGroundFormulas == None:
            relevantGroundFormulas = self.gndFormulas
            checkRelevance = True
        for gf in relevantGroundFormulas:
            # check if one of the ground atoms in the block appears in the ground formula
            if checkRelevance:
                isRelevant = False
                for i in block:
                    if i in gf.idxGroundAtoms():
                        isRelevant = True
                        break
                if not isRelevant: continue
            # make each one of the ground atoms in the block true once
            idxSum = 0
            for i in block:
                # set the current variable in the block to true
                world_values[idxGATrueone] = False
                world_values[i] = True
                # is the formula true?
                if gf.isTrue(world_values):
                    sums[idxSum] += wt[gf.idxFormula]
                # restore truth values
                world_values[i] = False
                world_values[idxGATrueone] = True
                idxSum += 1

        # if initialization values were used, reset them
        if mustRestoreValues:
            for i, value in enumerate(backupValues):
                world_values[block[i]] = value

        # return the list of exponentiated sums
        return map(exp, sums)

    def _getAtomExpsums(self, idxGndAtom, wt, world_values, relevantGroundFormulas=None):
        sums = [0, 0]
        # process all (relevant) ground formulas
        checkRelevance = False
        if relevantGroundFormulas == None:
            relevantGroundFormulas = self.gndFormulas
            checkRelevance = True
        old_tv = world_values[idxGndAtom]
        for gf in relevantGroundFormulas:
            if checkRelevance:
                if not gf.containsGndAtom(idxGndAtom):
                    continue
            for i, tv in enumerate([False, True]):
                world_values[idxGndAtom] = tv
                if gf.isTrue(world_values):
                    sums[i] += wt[gf.idxFormula]
                world_values[idxGndAtom] = old_tv
        return map(math.exp, sums)

    def _getAtom2BlockIdx(self):
        self.atom2BlockIdx = {}
        for idxBlock, (idxGA, block) in enumerate(self.pllBlocks):
            if block != None:
                for idxGA in block:
                    self.atom2BlockIdx[idxGA] = idxBlock
            else:
                self.atom2BlockIdx[idxGA] = idxBlock

    def __createPossibleWorlds(self, values, idx, code, bit):
        if idx == len(self.gndAtoms):
            if code in self.worldCode2Index:
                raise Exception("Too many possible worlds") # this actually never happens because Python can handle "infinitely" long ints
            self.worldCode2Index[code] = len(self.worlds)
            self.worlds.append({"values": values})
            if len(self.worlds) % 1000 == 0:
                #print "%d\r" % len(self.worlds)
                pass
            return
        # values that can be set for the truth value of the ground atom with index idx
        possible_settings = [True, False]
        # check if setting the truth value for idx is critical for a block (which is the case when idx is the highest index in a block)
        if idx in self.gndBlockLookup and POSSWORLDS_BLOCKING:
            block = self.gndBlocks[self.gndBlockLookup[idx]]
            if idx == max(block):
                # count number of true values already set
                nTrue, _ = 0, 0
                for i in block:
                    if i < len(values): # i has already been set
                        if values[i]:
                            nTrue += 1
                if nTrue >= 2: # violation, cannot continue
                    return
                if nTrue == 1: # already have a true value, must set current value to false
                    possible_settings.remove(True)
                if nTrue == 0: # no true value yet, must set current value to true
                    possible_settings.remove(False)
        # recursive descent
        for x in possible_settings:
            if x: offset = bit
            else: offset = 0
            self.__createPossibleWorlds(values + [x], idx + 1, code + offset, bit << 1)

    def _createPossibleWorlds(self):
        self.worldCode2Index = {}
        self.worlds = []
        self.__createPossibleWorlds([], 0, 0, 1)

    def getWorld(self, worldNo):
        '''
            gets the possible world with the given one-based world number
        '''
        self._getWorlds()
        return self.worlds[worldNo - 1]

    def _getWorlds(self):
        '''
            creates the set of possible worlds and calculates for each world all the necessary values
        '''
        if not hasattr(self, "worlds"):
            self._createPossibleWorlds()
            if self.mln.parameterType == 'weights':
                self._calculateWorldValues()
            elif self.mln.parameterType == 'probs':
                self._calculateWorldValues_prob()

    def _calculateWorldValues(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for worldIndex, world in enumerate(self.worlds):
            weights = []
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    weights.append(wts[gndFormula.idxFormula])
            exp_sum = exp(sum(weights))
            if self.mln.learnWtsMode != 'LL_ISE' or self.mln.allSoft == True or worldIndex != self.idxTrainingDB:
                total += exp_sum
            world["sum"] = exp_sum
            world["weights"] = weights
        self.partition_function = total

    def _calculateWorldExpSum(self, world, wts=None):
        if wts is None:
            wts = self._weights()
        sum = 0
        for gndFormula in self.gndFormulas:
            if self._isTrue(gndFormula, world):
                sum += wts[gndFormula.idxFormula]
        return math.exp(sum)

    def _countNumTrueGroundingsInWorld(self, idxFormula, world):
        numTrue = 0
        for gf in self.gndFormulas:
            if gf.idxFormula == idxFormula:
                if self._isTrue(gf, world["values"]):
                    numTrue += 1
        return numTrue

    def countWorldsWhereFormulaIsTrue(self, idxFormula):
        '''
        Counts the number of true groundings in each possible world and outputs a report
        with (# of true groundings, # of worlds with that number of true groundings).
        '''
        counts = {}
        for world in self.worlds:
            numTrue = self._countNumTrueGroundingsInWorld(idxFormula, world)
            old_cnt = counts.get(numTrue, 0)
            counts[numTrue] = old_cnt + 1
        print counts

    def countTrueGroundingsForEachWorld(self, appendToWorlds=False):
        '''
        Returns array of array of int a with a[i][j] = number of true groundings of j-th formula in i-th world
        '''
        all = []
        self._getWorlds()
        for world in self.worlds:
            counts = self.countTrueGroundingsInWorld(world["values"])
            all.append(counts)
            if appendToWorlds:
                world["counts"] = counts
        return all

    def countTrueGroundingsInWorld(self, world):
        '''
            computes the number of true groundings of each formula for the given world
            returns a vector v, where v[i] = number of groundings of the i-th MLN formula
        '''
        import numpy
        formulaCounts = numpy.zeros(len(self.mln.formulas), numpy.float64)                
        for gndFormula in self.mrf.mln.gndFormulas:
            if self._isTrue(gndFormula, world):
                formulaCounts[gndFormula.idxFormula] += 1
        return formulaCounts

    def _calculateWorldValues2(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for world in self.worlds:
            prob = 1.0
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    prob *= wts[gndFormula.idxFormula]
                else:
                    prob *= (1 - wts[gndFormula.idxFormula])
            world["prod"] = prob
            total += prob
        self.partition_function = total

    def _calculateWorldValues_prob(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for world in self.worlds:
            prod = 1.0
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    prod *= wts[gndFormula.idxFormula]
            world["prod"] = prod
            total += prod
        self.partition_function = total

    def _toCNF(self, allPositive=False):
        '''
            converts all ground formulas to CNF and also makes changes to the
            MLN's set of formulas, such that the correspondence between groundings
            and formulas still holds
        '''
        self.gndFormulas, self.formulas = toCNF(self.gndFormulas, self.formulas)

    def _isTrue(self, gndFormula, world_values):
        return gndFormula.isTrue(world_values)

    def printGroundFormulas(self, weight_transform=lambda x: x):
        for gf in self.gndFormulas:
            print "%7.3f  %s" % (weight_transform(self.formulas[gf.idxFormula].weight), strFormula(gf))
    
    def getGroundFormulas(self):
        '''
            returns a list of pairs (w, gf)
        '''
        return [(self.formulas[gf.idxFormula].weight, gf) for gf in self.gndFormulas]

    def printGroundAtoms(self):
        l = self.gndAtoms.keys()
        l.sort()
        for ga in l:
            print ga
            
    def strGroundAtom(self, idx):
        return str(self.gndAtomsByIdx[idx])

    def printState(self, world_values, showIndices=False):
        for idxGA, block in enumerate(self.pllBlocks):
            if idxGA != None:
                if showIndices: print "%-5d" % idxGA,
                print "%s=%s" % (str(self.gndAtomsByIdx[idxGA]), str(world_values[idxGA]))
            else:
                trueone = -1
                for i in block:
                    if world_values[i]:
                        trueone = i
                        break
                print "%s=%s" % (self._strBlock(block), str(self.gndAtomsByIdx[trueone]))

    # prints relevant data (including the entire state) for the given world (list of truth values) on a single line
    # for details see printWorlds
    def printWorld(self, world, mode=1, format=1):
        if "weights" in world and world["weights"] == []:
            world["weights"] = [0.0]
        literals = []
        for idx in range(len(self.gndAtoms)):
            if idx in self.gndBlockLookup: # process all gnd atoms in blocks in one go and only print the one that's true
                block = self.gndBlocks[self.gndBlockLookup[idx]]
                if idx == min(block): # process each block only once
                    maxlen = 0
                    gndAtom = None
                    for i in block:
                        maxlen = max(maxlen, len(str(self.gndAtomsByIdx[i])))
                        if world["values"][i]:
                            gndAtom = self.gndAtomsByIdx[i]
                    literal = "%-*s" % (maxlen, str(gndAtom))
                else:
                    continue
            else:
                gndAtom = str(self.gndAtomsByIdx[idx])
                value = world["values"][idx]
                literal = {True: " ", False:"!"}[value] + gndAtom
            literals.append(literal)
        if mode == 1:
            prob = world["sum"] / self.partition_function
            weights = "<- " + " ".join(map(lambda s: "%.1f" % s, world["weights"]))
            if format == 1: print "%6.2f%%  %s  %e <- %.2f %s" % (100 * prob, " ".join(literals), world["sum"], sum(world["weights"]), weights)
            elif format == 2: print "%6.2f%%  %s  %s" % (100 * prob, " ".join(literals), str(world["counts"]))
            #print "Pr=%.2f  %s  %15.0f" % (prob, " ".join(literals), world["sum"])
        elif mode == 2:
            print "%6.2f%%  %s  %.2f" % (100 * world["prod"] / self.partition_function, " ".join(literals), world["prod"])
        elif mode == 3:
            print " ".join(literals)

    # prints all the possible worlds implicitly defined by the set of constants with which the MLN was combined
    # Must call combine or combineDB beforehand if the MLN does not define at least one constant for every type/domain
    # The list contains for each world its 1-based index, its probability, the (conjunction of) literals, the exponentiated
    # sum of weights, the sum of weights and the individual weights that applied
    def printWorlds(self, sort=False, mode=1, format=1):
        self._getWorlds()
        if sort:
            worlds = list(self.worlds)
            worlds.sort(key=lambda x:-x["sum"])
        else:
            worlds = self.worlds
        print
        k = 1
        for world in worlds:
            print "%*d " % (int(math.ceil(math.log(len(self.worlds)) / math.log(10))), k),
            self.printWorld(world, mode=mode, format=format)
            k += 1
        print "Z = %f" % self.partition_function

    # prints the worlds where the given formula (condition) is true (otherwise same as printWorlds)
    def printWorldsFiltered(self, condition, mode=1, format=1):
        condition = fol.parseFormula(condition).ground(self, {})
        self._getWorlds()
        k = 1
        for world in self.worlds:
            if condition.isTrue(world["values"]):
                print "%*d " % (int(math.ceil(math.log(len(self.worlds)) / math.log(10))), k),
                self.printWorld(world, mode=mode, format=format)
                k += 1

    # prints the num worlds with the highest probability
    def printTopWorlds(self, num=10, mode=1, format=1):
        self._getWorlds()
        worlds = list(self.worlds)
        worlds.sort(key=lambda w:-w["sum"])
        for i in range(min(num, len(worlds))):
            self.printWorld(worlds[i], mode=mode, format=format)

    # prints, for the given world, the probability, the literals, the sum of weights, plus for each ground formula the truth value on a separate line
    def printWorldDetails(self, world):
        self.printWorld(world)
        for gf in self.gndFormulas:
            isTrue = gf.isTrue(world["values"])
            print "  %-5s  %f  %s" % (str(isTrue), self.formulas[gf.idxFormula].weight, strFormula(gf))

    def printFormulaProbabilities(self):
        self._getWorlds()
        sums = [0.0 for _ in range(len(self.formulas))]
        totals = [0.0 for i in range(len(self.formulas))]
        for world in self.worlds:
            for gf in self.gndFormulas:
                if self._isTrue(gf, world["values"]):
                    sums[gf.idxFormula] += world["sum"] / self.partition_function
                totals[gf.idxFormula] += world["sum"] / self.partition_function
        for i, formula in enumerate(self.formulas):
            print "%f %s" % (sums[i] / totals[i], str(formula))

    def printExpectedNumberOfGroundings(self):
        '''
            prints the expected number of true groundings of each formula
        '''
        self._getWorlds()
        counts = [0.0 for i in range(len(self.formulas))]
        for world in self.worlds:
            for gf in self.gndFormulas:
                if self._isTrue(gf, world["values"]):
                    counts[gf.idxFormula] += world["sum"] / self.partition_function
        #print counts
        for i, formula in enumerate(self.formulas):
            print "%f %s" % (counts[i], str(formula))

    def _fitProbabilityConstraints(self, probConstraints, fittingMethod=InferenceMethods.Exact, 
                                   fittingThreshold=1.0e-3, fittingSteps=20, fittingMCSATSteps=5000, 
                                   fittingParams=None, given=None, queries=None, verbose=True, 
                                   maxThreshold=None, greedy=False, probabilityFittingResultFileName=None, **args):
        '''
            applies the given probability constraints (if any), dynamically 
            modifying weights of the underlying MLN by applying iterative proportional fitting

            probConstraints: list of constraints
            inferenceMethod: one of the inference methods defined in InferenceMethods
            inferenceParams: parameters to pass on to the inference method
            given: if not None, fit parameters of posterior (given the evidence) rather than prior
            queries: queries to compute along the way, results for which will be returned
            threshold:
                when maximum absolute difference between desired and actual probability drops below this value, then stop (convergence)
            maxThreshold:
                if not None, then convergence is relaxed, and we stop when the *mean* absolute difference between desired and
                actual probability drops below "threshold" *and* the maximum is below "maxThreshold"
        '''
        inferenceMethod = fittingMethod
        threshold = fittingThreshold
        maxSteps = fittingSteps
        if fittingParams is None:
            fittingParams = {}
        inferenceParams = fittingParams
        inferenceParams["doProbabilityFitting"] = False # avoid recursive fitting calls when calling embedded inference method
        if given == None:
            given = ""
        if queries is None:
            queries = []
        if inferenceParams is None:
            inferenceParams = {}
        if len(probConstraints) == 0:
            if len(queries) > 0:
                pass # TODO !!!! because this is called from inferIPFPM, should perform inference anyhow
            return
        if verbose:
            print "applying probability fitting...(max. deviation threshold:", fittingThreshold, ")"
        t_start = time.time()

        # determine relevant formulas
        for req in probConstraints:
            # if we don't yet have a ground formula to fit, create one
            if not "gndFormula" in req:
                # if we don't yet have a formula to use, search for one that matches the expression to fit
                if not "idxFormula" in req:
                    idxFormula = None
                    for idxF, formula in enumerate(self.formulas):
                        #print strFormula(formula), req["expr"]
                        if strFormula(formula).replace(" ", "") == req["expr"]:
                            idxFormula = idxF
                            break
                    if idxFormula is None:
                        raise Exception("Probability constraint on '%s' cannot be applied because the formula is not part of the MLN!" % req["expr"])
                    req["idxFormula"] = idxFormula
                # instantiate a ground formula
                formula = self.formulas[req["idxFormula"]]
                vars = formula.getVariables(self)
                groundVars = {}
                for varName, domName in vars.iteritems(): # instantiate vars arbitrarily (just use first element of domain)
                    groundVars[varName] = self.domains[domName][0]
                gndFormula = formula.ground(self, groundVars)
                req["gndExpr"] = str(gndFormula)
                req["gndFormula"] = gndFormula

        # iterative fitting algorithm
        step = 1 # fitting round
        fittingStep = 1 # actual IPFP iteration
        #print "probConstraints", probConstraints, "queries", queries
        what = [r["gndFormula"] for r in probConstraints] + queries
        done = False
        while step <= maxSteps and not done:
            # calculate probabilities of the constrained formulas (ground formula)
            if inferenceMethod == InferenceMethods.Exact:
                if not hasattr(self, "worlds"):
                    self._getWorlds()
                else:
                    self._calculateWorldValues()
                results = self.inferExact(what, given=given, verbose=False, **inferenceParams)
            elif inferenceMethod == InferenceMethods.EnumerationAsk:
                results = self.inferEnumerationAsk(what, given=given, verbose=False, **inferenceParams)
            #elif inferenceMethod == InferenceMethods.ExactLazy:
            #    results = self.inferExactLazy(what, given=given, verbose=False, **inferenceParams)
            elif inferenceMethod == InferenceMethods.MCSAT:
                results = self.inferMCSAT(what, given=given, verbose=False, maxSteps = fittingMCSATSteps, **inferenceParams)
            else:
                raise Exception("Requested inference method (%s) not supported by probability constraint fitting" % InferenceMethods.getName(inferenceMethod))
            if type(results) != list:
                results = [results]
            # compute deviations
            diffs = [abs(r["p"] - results[i]) for (i, r) in enumerate(probConstraints)]
            maxdiff = max(diffs)
            meandiff = sum(diffs) / len(diffs)
            # are we done?
            done = maxdiff <= threshold
            if not done and maxThreshold is not None: # relaxed convergence criterion
                done = (meandiff <= threshold) and (maxdiff <= maxThreshold)
            if done:
                if verbose: print "  [done] dev max: %f mean: %f" % (maxdiff, meandiff)
                break
            # select constraint to fit
            if greedy:
                idxConstraint = diffs.index(maxdiff)
                strStep = "%d;%d" % (step, fittingStep)
            else:
                idxConstraint = (fittingStep - 1) % len(probConstraints)
                strStep = "%d;%d/%d" % (step, idxConstraint + 1, len(probConstraints))
            req = probConstraints[idxConstraint]
            # get the scaling factor and apply it
            formula = self.formulas[req["idxFormula"]]
            p = results[idxConstraint]
            #print "p", p, "results", results, "idxConstraint", idxConstraint
            pnew = req["p"]
            precision = 1e-3
            if p == 0.0: p = precision
            if p == 1.0: p = 1 - precision
            f = pnew * (1 - p) / p / (1 - pnew)
            old_weight = formula.weight
            formula.weight += float(logx(f)) #make sure to set the weight to a native float and not an mpmath value
            diff = diffs[idxConstraint]
            # print status
            if verbose: print "  [%s] p=%f vs. %f (diff = %f), weight %s: %f -> %f, dev max %f mean %f, elapsed: %.3fs" % (strStep, p, pnew, diff, strFormula(formula), old_weight, formula.weight, maxdiff, meandiff, time.time() - t_start)
            if fittingStep % len(probConstraints) == 0:
                step += 1
            fittingStep += 1

        #write resulting mln:
        if probabilityFittingResultFileName != None:
            mlnFile = file(probabilityFittingResultFileName, "w")
            self.mln.write(mlnFile)
            mlnFile.close()
            print "written MLN with probability constraints to:", probabilityFittingResultFileName

        return (results[len(probConstraints):], {"steps": min(step, maxSteps), "fittingSteps": fittingStep, "maxdiff": maxdiff, "meandiff": meandiff, "time": time.time() - t_start})

    # infer a probability P(F1 | F2) where F1 and F2 are formulas - using the default inference method specified for this MLN
    #   what: a formula, e.g. "foo(A,B)", or a list of formulas
    #   given: either
    #            * another formula, e.g. "bar(A,B) ^ !baz(A,B)"
    #              Note: it can be an arbitrary formula only for exact inference, otherwise it must be a conjunction
    #              This will overwrite any evidence previously set in the MLN
    #            * None if the evidence currently set in the MLN is to be used
    #   verbose: whether to print the results
    #   args: any additional arguments to pass on to the actual inference method
    def infer(self, what, given=None, verbose=True, **args):
        # call actual inference method
        defaultMethod = self.mln.defaultInferenceMethod
        if defaultMethod == InferenceMethods.Exact:
            return self.inferExact(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.GibbsSampling:
            return self.inferGibbs(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.MCSAT:
            return self.inferMCSAT(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.IPFPM_exact:
            return self.inferIPFPM(what, given, inferenceMethod=InferenceMethods.Exact, **args)
        elif defaultMethod == InferenceMethods.IPFPM_MCSAT:
            return self.inferIPFPM(what, given, inferenceMethod=InferenceMethods.MCSAT, **args)
        elif defaultMethod == InferenceMethods.EnumerationAsk:
            return self._infer(EnumerationAsk(self), what, given, verbose=verbose, **args)
        elif defaultMethod == InferenceMethods.WCSP:
            return self.inferWCSP(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.BnB:
            return self.inferBnB(what, given, verbose, **args)
        else:
            raise Exception("Unknown inference method '%s'. Use a member of InferenceMethods!" % str(self.defaultInferenceMethod))

    def inferExact(self, what, given=None, verbose=True, **args):
        return self._infer(ExactInference(self), what, given, verbose, **args)

    def inferExactLinear(self, what, given=None, verbose=True, **args):
        return self._infer(ExactInferenceLinear(self), what, given, verbose, **args)

    def inferEnumerationAsk(self, what, given=None, verbose=True, **args):
        return self._infer(EnumerationAsk(self), what, given, verbose, **args)

    def inferGibbs(self, what, given=None, verbose=True, **args):
        return self._infer(GibbsSampler(self), what, given, verbose=verbose, **args)

    def inferMCSAT(self, what, given=None, verbose=True, **args):
        self.mcsat = MCSAT(self, verbose=verbose) # can be used for later data retrieval
        self.mln.mcsat = self.mcsat # only for backwards compatibility
        return self._infer(self.mcsat, what, given, verbose, **args)

    def inferIPFPM(self, what, given=None, verbose=True, **args):
        '''
            inference based on the iterative proportional fitting procedure at the model level (IPFP-M)
        '''
        self.ipfpm = IPFPM(self) # can be used for later data retrieval
        self.mln.ipfpm = self.ipfpm # only for backwards compatibility
        return self._infer(self.ipfpm, what, given, verbose, **args)
    
    def inferWCSP(self, what, given=None, verbose=True, **args):
        '''
        Perform WCSP (MPE) inference on the MLN.
        '''
        return self._infer(WCSPInference(self), what, given, verbose, **args)
    
    def inferBnB(self, what, given=None, verbose=True, **args):
        return self._infer(BnBInference(self), what, given, verbose, **args)

    def _infer(self, inferObj, what, given=None, verbose=True, doProbabilityFitting=True, **args):
        # if there are prior probability constraints, apply them first
        if len(self.probreqs) > 0 and doProbabilityFitting:
            fittingParams = {
                "fittingMethod": self.mln.probabilityFittingInferenceMethod,
                "fittingSteps": self.mln.probabilityFittingMaxSteps,
                "fittingThreshold": self.mln.probabilityFittingThreshold,
                "probabilityFittingResultFileName": None
                #fittingMCSATSteps
            }
            fittingParams.update(args)
            self._fitProbabilityConstraints(self.probreqs, **fittingParams)
        # run actual inference method
        self.inferObj = inferObj
        return inferObj.infer(what, given, verbose=verbose, **args)

    def getResultsDict(self):
        '''
            gets the results computed by the last call to an inference method (infer*)
            in the form of a dictionary that maps ground formulas to probabilities
        '''
        return self.inferObj.getResultsDict()

    def _weights(self):
        ''' returns the weight vector as a list '''
        return [f.weight for f in self.formulas]
    
    def getRandomWorld(self):
        ''' uniformly samples from the set of possible worlds (taking blocks into account) '''
        self._getPllBlocks()
        state = [None] * len(self.gndAtoms)
        for _, (idxGA, block) in enumerate(self.pllBlocks):
            if block != None: # block of mutually exclusive atoms
                chosen = block[random.randint(0, len(block) - 1)]
                for idxGA in block:
                    state[idxGA] = (idxGA == chosen)
            else: # regular ground atom, which can either be true or false
                chosen = random.randint(0, 1)
                state[idxGA] = bool(chosen)
        return state

    def domSize(self, domName):
        return len(self.domains[domName])

    def writeDotFile(self, filename):
        '''
        write a .dot file for use with GraphViz (in order to visualize the current ground Markov network)
        '''
        if not hasattr(self, "gndFormulas") or len(self.gndFormulas) == 0:
            raise Exception("Error: cannot create graph because the MLN was not combined with a concrete domain")
        f = file(filename, "wb")
        f.write("graph G {\n")
        graph = {}
        for gf in self.gndFormulas:
            idxGndAtoms = gf.idxGroundAtoms()
            for i in range(len(idxGndAtoms)):
                for j in range(i + 1, len(idxGndAtoms)):
                    edge = [idxGndAtoms[i], idxGndAtoms[j]]
                    edge.sort()
                    edge = tuple(edge)
                    if not edge in graph:
                        f.write("  ga%d -- ga%d\n" % edge)
                        graph[edge] = True
        for gndAtom in self.gndAtoms.values():
            f.write('  ga%d [label="%s"]\n' % (gndAtom.idx, str(gndAtom)))
        f.write("}\n")
        f.close()

    def writeGraphML(self, filename):
        import graphml
        G = graphml.Graph()
        nodes = []
        for i in xrange(len(self.gndAtomsByIdx)):
            ga = self.gndAtomsByIdx[i]
            nodes.append(graphml.Node(G, label=str(ga), shape="ellipse", color=graphml.randomVariableColor))
        links = {}
        for gf in self.gndFormulas:
            print gf
            idxGAs = sorted(gf.idxGroundAtoms())
            for idx, i in enumerate(idxGAs):
                for j in idxGAs[idx+1:]:
                    t = (i,j)
                    if not t in links:
                        print "  %s -- %s" % (nodes[i], nodes[j])
                        graphml.UndirectedEdge(G, nodes[i], nodes[j])
                        links[t] = True
        f = open(filename, "w")
        G.write(f)
        f.close()

def readMLNFromFile(filename_or_list, verbose=False):
    '''
    Reads an MLN object from a file or a set of files.
    '''
    # read MLN file
    text = ""
    if filename_or_list is not None:
        if not type(filename_or_list) == list:
            filename_or_list = [filename_or_list]
        for filename in filename_or_list:
            #print filename
            f = file(filename)
            text += f.read()
            f.close()
    formulatemplates = []
    if text == "": 
        raise Exception("No MLN content to construct model from was given; must specify either file/list of files or content string!")
    # replace some meta-directives in comments
    text = re.compile(r'//\s*<group>\s*$', re.MULTILINE).sub("#group", text)
    text = re.compile(r'//\s*</group>\s*$', re.MULTILINE).sub("#group.", text)
    # remove comments
    text = stripComments(text)
    mln = MLN()
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
                filename = line[len("#include "):].strip()
                content = stripComments(file(filename, "r").read())
                lines = content.split("\n") + lines[iLine:]
                iLine = 0
                continue
            elif line.startswith('#unique'):
                try:
                    uniVars = re.search('#unique{(.+)\w*,\w*(.+)}', line)
                    uniVars = uniVars.groups()
                    if len(uniVars) != 2: raise
                    nextFormulaUnique = uniVars
                except:
                    raise Exception('Malformed #unique expression: "%s"' % line)
                continue
            elif line.startswith("#fixUnitary:"): # deprecated (use instead #fixedWeightFreq)
                predName = line[12:len(line)]
                if hasattr(mln, 'fixationSet'):
                    mln.fixationSet.add(predName)
                else:
                    mln.fixationSet = set([predName])
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
            if '{' in line:
                domName, constants = parseDomDecl(line)
                if domName in mln.domains: raise Exception("Domain redefinition: '%s' already defined" % domName)
                mln.staticDomains[domName] = constants
                mln.domDecls.append(line)
                continue
            # prior probability requirement
            if line.startswith("P("):
                m = re.match(r"P\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise Exception("Prior probability constraint formatted incorrectly: %s" % line)
                mln.probreqs.append({"expr": strFormula(fol.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # posterior probability requirement/soft evidence
            if line.startswith("R(") or line.startswith("SE("):
                m = re.match(r"(?:R|SE)\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise Exception("Posterior probability constraint formatted incorrectly: %s" % line)
                mln.posteriorProbReqs.append({"expr": strFormula(fol.parseFormula(m.group(1))).replace(" ", ""), "p": float(m.group(2))})
                continue
            # variable definition
            if line.startswith("$"):
                m = re.match(r'(\$\w+)\s*=(.+)', line)
                if m is None:
                    raise Exception("Variable assigment malformed: %s" % line)
                mln.vars[m.group(1)] = "(%s)" % m.group(2).strip()
                continue
            # mutex constraint
            if re.search(r"[a-z_][-_'a-zA-Z0-9]*\!", line) != None:
                pred = parsePredicate(line)
                mutex = []
                for param in pred[1]:
                    if param[-1] == '!':
                        mutex.append(True)
                    else:
                        mutex.append(False)
                mln.blocks[pred[0]] = mutex
                # if the corresponding predicate is not yet declared, take this to be the declaration
                if not pred[0] in mln.predDecls:
                    argTypes = map(lambda x: x.strip("!"), pred[1])
                    mln.predDecls[pred[0]] = argTypes
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
                        pred = predDecl.parseString(line)[0]
                    except Exception, e:
                        isPredDecl = False
                if isPredDecl:
                    predName = pred[0]
                    if predName in mln.predDecls:
                        raise Exception("Predicate redefinition: '%s' already defined" % predName)
                    mln.predDecls[predName] = list(pred[1])
                    continue
                else:
                    # formula (template) with weight or terminated by '.'
                    if not isHard:
                        spacepos = line.find(' ')
                        weight = line[:spacepos]
                        formula = line[spacepos:].strip()
                    try:
                        formula = logic.grammar.parseFormula(formula)
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
                        raise Exception("Error parsing formula '%s'\n" % formula)
        except:
            sys.stderr.write("Error processing line '%s'\n" % line)
            cls, e, tb = sys.exc_info()
            traceback.print_tb(tb)
            raise e

    # augment domains with constants appearing in formula templates
    for f in formulatemplates:
        constants = {}
        f.getVariables(mln, None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: mln.addConstant(domain, c)
    
    # save data on formula templates for materialization
    mln.uniqueFormulaExpansions = uniqueFormulaExpansions
    mln.formulaTemplates = formulatemplates
    mln.templateIdx2GroupIdx = templateIdx2GroupIdx
    mln.fixedWeightTemplateIndices = fixedWeightTemplateIndices
    return mln