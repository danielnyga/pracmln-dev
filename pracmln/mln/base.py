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

from pracmln.logic import FirstOrderLogic, FuzzyLogic

from string import whitespace

# from learning import *
# from inference import *

import platform
from methods import InferenceMethods, LearningMethods
from mrf import MRF
from errors import MLNParsingError
# from experimental.mlnboost import MLNBoost
from pyparsing import ParseException
from pracmln.mln.constants import HARD, comment_color, predicate_color, weight_color
import copy
import os
import logging
from pracmln.mln.util import StopWatch, fstr, mergedom, colorize, stripComments, out
from pracmln.mln.mlnpreds import Predicate, FuzzyPredicate, SoftFunctionalPredicate,\
    FunctionalPredicate
from pracmln.mln.database import Database
from pracmln.mln.learning.multidb import MultipleDatabaseLearner
import sys
import re
import traceback


logger = logging.getLogger(__name__)


if platform.architecture()[0] == '32bit':
    try:
        if not DEBUG:
            import psyco # Don't use Psyco when debugging! @UnresolvedImport
            psyco.full()
    except:
        logger.warning("Note: Psyco (http://psyco.sourceforge.net) was not loaded. On 32bit systems, it is recommended to install it for improved performance.\n")





class MLN(object):
    '''
    Represents a Markov logic network.
    
    :member formulas:    a list of `MLNFormula` objects representing the formulas of the MLN.
    :member predicates:  a dict mapping predicate names to `Predicate` objects.
    
    :param logic:        (string) the type of logic to be used in this MLN. Possible values
                         are `FirstOrderLogic` and `FuzzyLogic`.
    :param grammar:      (string) the syntax to be used. Possible grammars are
                         `PRACGrammar` and `StandardGrammar`.
    :param mlnfile:      can be a path to an MLN file or a file object.
    '''
    

    def __init__(self, logic='FirstOrderLogic', grammar='PRACGrammar', mlnfile=None):
        log = logging.getLogger(self.__class__.__name__)
        # instantiate the logic and grammar
        logic_str = '%s("%s", self)' % (logic, grammar)
        self.logic = eval(logic_str)
        log.debug('Creating MLN with %s syntax and %s semantics' % (grammar, logic))
        
        self._predicates = {} # maps from predicate name to the predicate instance
        self.domains = {}    # maps from domain names to list of values
        self._formulas = []   # list of MLNFormula instances
        self.domain_decls = []
        self.weights = []
        self.fixweights = []
        self.vars = {}
        self._unique_templvars = []
        self._probreqs = []
        self._materialized = False
        
        if mlnfile is not None:
            if isinstance(mlnfile, basestring):
                f = open(mlnfile, 'r')
                MLN.load(mlnfile, logic=logic, grammar=grammar, mln=self)
                f.close()
            else:
                MLN.load(mlnfile, logic=logic, grammar=grammar, mln=self)
            return
        
        self.closedWorldPreds = []

        self.formulaGroups = []
        self.templateIdx2GroupIdx = {}

        self.posteriorProbReqs = []
#         self.parameterType = parameterType
        self.probabilityFittingInferenceMethod = InferenceMethods.Exact
        self.probabilityFittingThreshold = 0.002 # maximum difference between desired and computed probability
        self.probabilityFittingMaxSteps = 20 # maximum number of steps to run iterative proportional fitting
#         self.defaultInferenceMethod = defaultInferenceMethod
        self.allSoft = False
        self.watch = StopWatch()


    @property
    def predicates(self):
        return list(self.iterpreds())
     
    
    @property
    def formulas(self):
        return list(self._formulas)
        

    @property
    def weights(self):
        return self._weights
    
    
    @weights.setter
    def weights(self, wts):
        if len(wts) != len(self._formulas):
            raise Exception('Weight vector must have the same length as formula vector.')
        wts = map(lambda w: float('%-10.6f' % float(eval(str(w)))) if type(w) in (float, int) and w is not HARD else w, wts)
        self._weights = wts
    
        
    @property
    def fixweights(self):
        return self._fixweights
    
    
    @fixweights.setter
    def fixweights(self, fw):
        self._fixweights = fw
    
    
    @property
    def probreqs(self):
        return self._probreqs
    
    @property
    def weighted_formulas(self):
        return [f for f in self._formulas if f.weight is not HARD]
    
    
    @property
    def prednames(self):
        return [p.name for p in self.predicates]


    def prior(self, f, p):
        self._probreqs.append(FirstOrderLogic.PriorConstraint(formula=f, p=p))
    
        
    def posterior(self, f, p):
        self._probreqs.append(FirstOrderLogic.PosteriorConstraint(formula=f, p=p))


    def copy(self):
        '''
        Returns a deep copy of this MLN, which is not yet materialized.
        '''
        mln_ = MLN(logic=self.logic.__class__.__name__, grammar=self.logic.grammar.__class__.__name__)
        for pred in self.iterpreds():
            mln_.predicate(copy.copy(pred))
        mln_.domain_decls = list(self.domain_decls)
        for i, f in self.iterformulas():
            mln_.formula(f.copy(mln=mln_), weight=self.weight(i), fixweight=self.fixweights[i], unique_templvars=self._unique_templvars[i])
        mln_.domains = dict(self.domains)
        mln_.vars = dict(self.vars)
        mln_._probreqs = list(self.probreqs)
        return mln_
    
    
    def predicate(self, predicate):
        '''
        Returns the predicate object with the given predicate name, or declares a new predicate.
        
        If predicate is a string, this method returns the predicate object 
        assiciated to the given predicate name. If it is a predicate instance, it declares the
        new predicate in this MLN and returns the MLN instance. In the latter case, this is 
        equivalent to `MLN.declare_predicate()`.
        
        :param predicate:    name of the predicate to be returned or a `Predicate` instance
                             specifying the predicate to be declared.
        :returns:            the Predicate object or None if there is no predicate with this name.
                             If a new predicate is declared, returns this MLN instance.
                             
        :Example:
        
        >>> mln = MLN()
        >>> mln.predicate(Predicate(foo, [arg0, arg1]))
               .predicate(Predicate(bar, [arg1, arg2])) # this declares predicates foo and bar
        >>> mln.predicate('foo')
        <Predicate: foo(arg0,arg1)>
        
        '''
        if isinstance(predicate, Predicate):
            return self.declare_predicate(predicate)
        elif isinstance(predicate, basestring):
            return self._predicates.get(predicate, None)
        else:
            raise Exception('Illegal type of argument predicate: %s' % type(predicate))
        
        
    def iterpreds(self):
        '''
        Yields the predicates defined in this MLN alphabetically ordered.
        '''
        for predname in sorted(self._predicates):
            yield self.predicate(predname)
    
    
    def update_predicates(self, mln):
        '''
        Merges the predicate definitions of this MLN with the definitions
        of the given one.
        
        :param mln:     an instance of an MLN object.
        '''
        for pred in mln.iter_predicates():
            self.declare_predicate(pred)
    

    def declare_predicate(self, predicate):
        '''
        Adds a predicate declaration to the MLN:
        
        :param predicate:      an instance of a Predicate or one of its subclasses 
                               specifying a predicate declaration.
        '''
        pred = self._predicates.get(predicate.name)
        if pred is not None and  pred != predicate:
            raise Exception('Contradictory predicate definitions: %s <--> %s' % (pred, predicate))
        else:
            self._predicates[predicate.name] = predicate
            for dom in predicate.argdoms:
                if dom not in self.domains:
                    self.domains[dom] = []
        return self

            
    def formula(self, formula, weight=0., fixweight=False, unique_templvars=None):
        '''
        Adds a formula to this MLN. The respective domains of constants
        are updated, if necessary. If `formula` is an integer, returns the formula
        with the respective index or the formula object that has been created from
        formula. The formula will be automatically tied to this MLN.
        
        :param formula:             a `Logic.Formula` object or a formula string
        :param weight:              an optional weight. May be a mathematical expression
                                    as a string (e.g. log(0.1)), real-valued number
                                    or `mln.infty` to indicate a hard formula.
        :param fixweight:           indicates whether or not the weight of this
                                    formula should be fixed during learning.
        :param unique_templvars:    specifies a list of template variables that will create
                                    only unique combinations of expanded formulas
        '''
        if isinstance(formula, basestring):
            formula = self.logic.parse_formula(formula)
        elif type(formula) is int:
            return self._formulas[formula]
        constants = {}
        formula.vardoms(None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: self.constant(domain, c)
        formula.mln = self
        formula.idx = len(self._formulas)
        self._formulas.append(formula)
        self.weights.append(weight)
        self.fixweights.append(fixweight)
        self._unique_templvars.append(list(unique_templvars) if unique_templvars is not None else [])
        return self._formulas[-1]
    
    
    def _rmformulas(self):
        self._formulas = []
        self.weights = []
        self.fixweights = []
        self._unique_templvars = []
    
    
    def iterformulas(self):
        '''
        Returns a generator yielding (idx, formula) tuples.
        '''
        for i, f in enumerate(self._formulas):
            yield i, f
    
    
    def weight(self, idx, weight=None):
        '''
        Returns or sets the weight of the formula with index `idx`.
        '''
        if weight is not None:
            self.weights[idx] = weight
        else:
            return self.weights[idx]
    
    
    def __lshift__(self, input):
        parse_mln(input, '.', logic=None, grammar=None, mln=self)
    
                
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
        materialized_mln = self.materializeFormulaTemplates([evidence_db], verbose=self.verbose)
        mrf = materialized_mln.groundMRF(evidence_db, simplify=True, groundingMethod='FastConjunctionGrounding', **params)
        
        resultDict = mrf.infer(what=queries, given=None, **params)
        log.debug(resultDict)
        result_db = Database(self)
        for atom in sorted(resultDict):
            value = resultDict[atom]
            result_db.addGroundAtom(atom, value)
            if value > 0:
                log.info("%.3f    %s" % (value, atom))
        if params.get('mergeDBs', True):
            return result_db.union(None, evidence_db)
        else:
            return result_db 
        
                
    def materialize(self, *dbs):
        '''
        Materializes this MLN with respect to the databases given. This must
        be called before learning or inference can take place.
        
        Returns a new MLN instance containing expanded formula templates and
        materialized weights. Normally, this method should not be called from the outside. 
        Also takes into account whether or not particular domain values or predictaes
        are actually used in the data, i.e. if a predicate is not used in any
        of the databases, all formulas that make use of this predicate are ignored.

        :param *dbs:     list of `Database` objects for materialization.
        '''
        logger = logging.getLogger(self.__class__.__name__)
        logger.debug("materializing formula templates...")
        
        mln_ = self.copy()

        # obtain full domain with all objects 
        fulldomain = mergedom(self.domains, *[db.domains for db in dbs])
        logger.debug('full domains: %s' % fulldomain)
        
        # collect the admissible formula templates. templates might be not
        # admissible since the domain of a template variable might be empty.
        for ft in list(mln_.formulas):
            domnames = ft.vardoms().values()
            if any([not domname in fulldomain for domname in domnames]):
                logger.debug('Discarding formula template %s, since it cannot be grounded (domain(s) %s empty).' % \
                    (fstr(ft), ','.join([d for d in domnames if d not in fulldomain])))
                mln_.rmf(ft)
        # collect the admissible predicates. a predicate may become inadmissible
        # if either the domain of one of its arguments is empty or there is
        # no formula containing the respective predicate.
        predicates_used = set()
        for _, f in mln_.iterformulas():
            predicates_used.update(f.prednames())
        for predicate in self.iterpreds():
            remove = False
            if any([not dom in fulldomain for dom in predicate.argdoms]):
                logger.debug('Discarding predicate %s, since it cannot be grounded.' % (predicate.name))
                remove = True
            if predicate.name not in predicates_used:
                logger.debug('Discarding predicate %s, since it is unused.' % predicate.name)
                remove = True
            if remove:  del mln_._predicates[predicate.name]
            
        # permanently transfer domains of variables that were expanded from templates
        for _, ft in mln_.iterformulas():
            domnames = ft.template_variables().values()
            for domname in domnames:
                mln_.domains[domname] = fulldomain[domname]

        # materialize the formula templates
        mln__ = mln_.copy()
        mln__ ._rmformulas()
        for i, template in mln_.iterformulas():
            for variant in template.template_variants():
                idx = len(mln__._formulas)
                f = mln__.formula(variant, weight=template.weight if isinstance(template.weight, basestring) else template.weight, 
                                  fixweight=mln_.fixweights[i])
                f.idx = idx
        mln__._materialized = True
        return mln__


    def constant(self, domain, *values):
        '''
        Adds to the MLN a constant domain value to the domain specified.
        
        If the domain doesn't exist, it is created.
        
        :param domain:    (string) the name of the domain the given value shall be added to.
        :param values:     (string) the values to be added.
        '''
        if domain not in self.domains: self.domains[domain] = []
        dom = self.domains[domain]
        for value in values:
            if value not in dom: dom.append(value)
        return self


    def ground(self, db, cw=False, cwpreds=None, **params):
        '''
        Creates and returns a ground Markov Random Field for the given database.
        
        :param db:         database filename (string) or Database object
        :param cw:         if the closed-world assumption shall be applied (to all predicates)
        :param cwpreds:    a list of predicate names the closed-world assumption shall be applied.
        '''
        logger = logging.getLogger(self.__class__.__name__)
        logger.debug('creating ground MRF...')
        mrf = MRF(self, db)
        for pred in self.predicates:
            for gndatom in pred.groundatoms(self, mrf.domains):
                mrf.gndatom(gndatom.predname, *gndatom.args)
        evidence = dict([(atom, value) for atom, value in db.evidence.iteritems() if mrf.gndatom(atom) is not None])
        mrf.set_evidence(evidence, erase=False)
        if cw and cwpreds is not None:
            raise Exception('Conflicting parameters: cw and cwpreds are both given.')
        if cw: mrf.apply_cw()
        elif cwpreds is not None:
            mrf.apply_cw(*cwpreds)
        return mrf


    def update_domain(self, domain):
        '''
        Combines the existing domain (if any) with the given one.
        
        :param domain: a dictionary with domain Name to list of string constants to add
        '''
        for domname in domain: break
        for value in domain[domname]:
            self.constant(domname, value)


    def learn(self, databases, method=LearningMethods.BPLL, **params):
        '''
        Triggers the learning parameter learning process for a given set of databases.
        Returns a new MLN object with the learned parameters.
        
        :param databases:     list of :class:`mln.database.Database` objects or filenames
        '''
        log = logging.getLogger(self.__class__.__name__)
        self.verbose = params.get('verbose', False)
        # get a list of database objects
        if len(databases) == 0:
            log.exception('At least one database is needed for learning.')
        dbs = []

        for db in databases:
            if type(db) == str:
                db = Database.load(self, db)
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
        formula_templates = list(self.formulas)
        newMLN = self.materializeFormulaTemplates(dbs, self.verbose)
        if method == LearningMethods.MLNBoost:
            newMLN.formulas = formula_templates

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
        elif params.get('incremental', False): 
            learner = IncrementalLearner(newMLN, method, dbs, **params)
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
        
        if params.get('ignoreZeroWeightFormulas', False):
            for f in list(learnedMLN.formulas):
                if f.weight == 0:
                    mln.formulas.remove(f)
        
        if self.verbose:
            learnedMLN.write(sys.stdout, color=True)
#             print "\n// formulas"
#             for formula in learnedMLN.formulas:
#                 print "%f  %s" % (float(eval(str(formula.weight))), strFormula(formula))
        return learnedMLN


    def tofile(self, filename):
        '''
        Creates the file with the given filename and writes this MLN into it.
        '''
        f = open(filename, 'w+')
        self.write(f, color=False)   
        f.close()


    def write(self, stream=sys.stdout, color=None):
        '''
        Writes the MLN to the given stream.
        
        The default stream is `sys.stdout`. In order to print the MLN to the console, a simple
        call of `mln.write()` is sufficient. If color is not specified (is None), then the
        output to the console will be colored and uncolored for every other stream. 
        
        :param stream:        the stream to write the MLN to.
        :param color:         whether or not output should be colorized.
        '''
        if color is None:
            if stream != sys.stdout: 
                color = False
            else: color = True
        if 'learnwts_message' in dir(self):
            stream.write("/*\n%s*/\n\n" % self.learnwts_message)
        # domain declarations
        if self.domain_decls: stream.write(colorize("// domain declarations\n", comment_color, color))
        for d in self.domain_decls: 
            stream.write("%s\n" % d)
        stream.write('\n')
        # variable definitions
        if self.vars: stream.write(colorize('// variable definitions\n', comment_color, color))
        for var, val in self.vars.iteritems():
            stream.write('%s = %s' % (var, val))
        stream.write('\n')
        stream.write(colorize("\n// predicate declarations\n", comment_color, color))
        for predicate in self.iterpreds():
            if isinstance(predicate, FuzzyPredicate):
                stream.write('#fuzzy\n')
            stream.write("%s(%s)\n" % (colorize(predicate.name, predicate_color, color), predicate.argstr()))
        stream.write(colorize("\n// formulas\n", comment_color, color))
        for idx, formula in self.iterformulas():
            if self._unique_templvars[idx]:
                stream.write('#unique{%s}\n' % ','.join(self._unique_templvars[idx]))
            if formula.weight == HARD:
                stream.write("%s.\n" % fstr(formula.cstr(color)))
            else:
                try:
                    w = colorize("%-10.6f", weight_color, color) % float(eval(str(formula.weight)))
                except:
                    w = colorize(str(formula.weight), weight_color, color)
                stream.write("%s  %s\n" % (w, fstr(formula.cstr(color))))


    def print_formulas(self):
        '''
        Nicely prints the formulas and their weights.
        '''
        for f in self.iterFormulasPrintable():
            print f

                
    def iter_formulas_printable(self):
        '''
        Iterate over all formulas, yield nicely formatted strings.
        '''
        formulas = sorted(self.formulas)
        for f in formulas:
            if f.weight == HARD:
                yield '%s.' % fstr(f)
            elif type(f.weight) is float:
                yield "%-10.6f\t%s" % (f.weight, fstr(f))
            else:
                yield "%s\t%s" % (str(f.weight), fstr(f))
        
        
    @staticmethod
    def load(files, logic='FirstOrderLogic', grammar='PRACGrammar', mln=None):
        '''
        Reads an MLN object from a file or a set of files.
        
        :param files:     one or more file names of .mln files. If multiple file names are given,
                          the contents of all files will be concatenated.
        :param logic:     (string) the type of logic to be used. Either `FirstOrderLogic` or `FuzzyLogic`.
        :param grammar:   (string) the syntax to be used for parsing the MLN file. Either `PRACGrammar` or `StandardGrammar`.
        '''
        # read MLN file
        text = ""
        if files is not None:
            if not type(files) == list:
                files = [files]
            for filename in files:
                f = file(filename)
                text += f.read()
                f.close()
        dirs = [os.path.dirname(fn) for fn in files]
        return parse_mln(text, searchPath=dirs[0], logic=logic, grammar=grammar, mln=mln)


def parse_mln(text, searchPath='.', logic='FirstOrderLogic', grammar='PRACGrammar', mln=None):
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
    if mln is None:
        mln = MLN(logic, grammar)
    # read lines
    mln.hard_formulas = []
    templateIdx2GroupIdx = {}
    inGroup = False
    idxGroup = -1
    fixWeightOfNextFormula = False
    fuzzy = False
    uniquevars = None
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
            elif line.startswith("#fixweight"):
                fixWeightOfNextFormula = True
                continue
            elif line.startswith('#fuzzy'):
                if not isinstance(mln.logic, FuzzyLogic):
                    raise Exception('Fuzzy declarations are not allowed in %s' % mln.logic.__class__.__name__)
                fuzzy = True
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
                    uniVars = map(str.strip, uniVars.split(','))
                    uniquevars = uniVars
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
                parse = mln.logic.parse_domain(line)
                if parse is not None:
                    domName, constants = parse
                    domName = str(domName)
                    constants = map(str, constants)
                    if domName in mln.domains: 
                        log.debug("Domain redefinition: Domain '%s' is being updated with values %s." % (domName, str(constants)))
                    if domName not in mln.domains:
                        mln.domains[domName] = []
                    mln.constant(domName, *constants)
                    mln.domain_decls.append(line)
                    continue
            # prior probability requirement
            if line.startswith("P("):
                m = re.match(r"P\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Prior probability constraint formatted incorrectly: %s" % line)
                mln.prior(f=mln.logic.parse_formula(m.group(1)), p=float(m.group(2)))
                continue
            # posterior probability requirement/soft evidence
            if line.startswith("R(") or line.startswith("SE("):
                m = re.match(r"(?:R|SE)\((.*?)\)\s*=\s*([\.\de]+)", line)
                if m is None:
                    raise MLNParsingError("Posterior probability constraint formatted incorrectly: %s" % line)
                mln.posterior(f=mln.logic.parse_formula(m.group(1)), p=float(m.group(2)))
                continue
            # variable definition
            if re.match(r'(\$\w+)\s*=(.+)', line):
                m = re.match(r'(\$\w+)\s*=(.+)', line)
                if m is None:
                    raise MLNParsingError("Variable assigment malformed: %s" % line)
                mln.vars[m.group(1)] = "%s" % m.group(2).strip()
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
                        pred = mln.logic.parse_predicate(line)
                    except Exception, e:
                        isPredDecl = False
                if isPredDecl:
                    predname = str(pred[0])
                    argdoms = map(str, pred[1])
                    softmutex = False
                    mutex = None
                    for i, dom in enumerate(argdoms):
                        if dom[-1] in ('!', '?'):
                            if mutex is not None:
                                raise Exception('More than one arguments are specified as (soft-)functional') 
                            if fuzzy: raise Exception('(Soft-)functional predicates must not be fuzzy.')
                            mutex = i
                        if dom[-1] == '?': softmutex = True
                    argdoms = map(lambda x: x.strip('!?'), argdoms)
                    pred = None
                    if mutex is not None:
                        if softmutex:
                            pred = SoftFunctionalPredicate(predname, argdoms, mutex)
                        else:
                            pred = FunctionalPredicate(predname, argdoms, mutex)
                    elif fuzzy:
                        pred = FuzzyPredicate(predname, argdoms)
                    else:
                        pred = Predicate(predname, argdoms)
                    mln.predicate(pred)
                    continue
                else:
                    # formula (template) with weight or terminated by '.'
                    if not isHard:
                        spacepos = line.find(' ')
                        weight = line[:spacepos]
                        formula = line[spacepos:].strip()
                    try:
                        formula = mln.logic.parse_formula(formula)
                        if isHard:
                            weight = HARD # not set until instantiation when other weights are known
                        idxTemplate = len(formulatemplates)
                        formulatemplates.append(formula)
                        fixweight = False
                        if inGroup:
                            templateIdx2GroupIdx[idxTemplate] = idxGroup
                        if fixWeightOfNextFormula == True:
                            fixWeightOfNextFormula = False
                            fixweight = True
                            fixedWeightTemplateIndices.append(idxTemplate)
                        mln.formula(formula, weight, fixweight, uniquevars)
                        if uniquevars:
                            uniquevars = None
                    except ParseException, e:
                        raise MLNParsingError("Error parsing formula '%s'\n" % formula)
                if fuzzy and not isPredDecl: raise Exception('"#fuzzy" decorator not allowed at this place.')
        except MLNParsingError:
            sys.stderr.write("Error processing line '%s'\n" % line)
            cls, e, tb = sys.exc_info()
            traceback.print_tb(tb)
            raise MLNParsingError(e.message)

    # augment domains with constants appearing in formula templates
    for _, f in mln.iterformulas():
        constants = {}
        f.vardoms(None, constants)
        for domain, constants in constants.iteritems():
            for c in constants: mln.constant(domain, c)
    
    # save data on formula templates for materialization
#     mln.uniqueFormulaExpansions = uniqueFormulaExpansions
    mln.templateIdx2GroupIdx = templateIdx2GroupIdx
#     mln.fixedWeightTemplateIndices = fixedWeightTemplateIndices
    return mln



