#
# Markov Logic Networks -- Databases
#
# (C) 2006-2013 by Daniel Nyga, (nyga@cs.tum.edu)
#                  Dominik Jain (jain@cs.tum.edu)
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
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.'''

from util import stripComments,mergeDomains
import copy
from praclog import logging
from logic.common import Logic
from errors import NoSuchPredicateError
from utils import colorize
from logic.fol import FirstOrderLogic
import os
from StringIO import StringIO

class Database(object):
    '''
    Represents an MLN Database, which is a set of ground literals (i.e. ground
    atoms or negated ground atoms)
    
    Attributes:
        mln (`MLN`):        the respective MLN object that this Database is associated to
        domains (`dict`):    the variable domain specific to this data base (i.e. without
                          values from the MLN domains which are not present in the DB.
        evidence (`dict`):    dictionary mapping ground atom strings to truth values
    '''
    
    def __init__(self, mln):
        '''
        Creates a new, empty `Database` object.
        
        Args:
            mln (`MLN`):    The Markov Logic Network this `Database` should be attached to.
        '''
        self.mln = mln
        self.domains = {}
        self.evidence = {}
#         self.softEvidence = []
        self.includeNonExplicitDomains = True
        
    def duplicate(self, mln=None, ignoreUnknownPredicates=False):
        '''
        Returns a deep copy this Database. If mln is specified, asserts
        this database for the given MLN.
        '''
        if mln is None:
            db = Database(self.mln)
            db.domains = copy.deepcopy(self.domains)
            db.evidence = copy.deepcopy(self.evidence)
#             db.softEvidence = copy.deepcopy(self.softEvidence)
        else:
            db = Database(mln)
            for truth, atom in self.iterGroundLiteralStrings():
                try: db.addGroundAtom(atom, truth)
                except NoSuchPredicateError: pass
        return db
    
    
    def union(self, mln=None, *dbs):
        '''
        Returns a new database consisting of the union of all databases
        given in the arguments. If mln is specified, the new database will
        be attached to that one, otherwise the mln of this database will
        be used.
        '''
        result_db = Database(mln if mln is not None else self.mln)
        for db in [self] + list(dbs):
            for atom, truth in db.evidence.iteritems():
                try:
                    result_db.addGroundAtom(atom, truth)
                except NoSuchPredicateError: pass
        return result_db
    

    def iterGroundLiteralStrings(self, pred_names=None):
        '''
        Iterates over all ground literals in this database that match any of
        the given predicate names. If no predicate is specified, it
        yields all ground literals.
        '''
        for atom, truth in self.evidence.iteritems():
            if pred_names is not None:
                _, predName, _ = self.mln.logic.parseLiteral(atom)
                if not predName in pred_names:
                    continue
            yield truth, atom

    def addGroundAtom(self, gndLit, truth=1):
        '''
        Adds the fact represented by the ground atom, which might be
        a GroundLit object or a string.
        '''
        if type(gndLit) is str:
            isTrue, predName, params = self.mln.logic.parseLiteral(gndLit)
            atomString = "%s(%s)" % (predName, ",".join(params))
        elif isinstance(gndLit, Logic.GroundLit):
            atomString = str(gndLit.gndAtom)
            isTrue = not gndLit.negated
            predName = gndLit.gndAtom.predName
            params = gndLit.gndAtom.params
        else:
            raise Exception('gndLit has an illegal type: %s' % type(gndLit))
        truth = truth if isTrue else 1 - truth
        truth = eval('%.6f' % truth)
        # update the domains
        domNames = self.mln.predicates.get(predName, None)
        if domNames is None:
            raise NoSuchPredicateError('No such predicate: %s' % predName)
        if len(domNames) != len(params):
            raise Exception('Invalid number of arguments: %s' % str(gndLit))
        for i, domName in enumerate(domNames):
            dom = self.domains.get(domName, None)
            if dom is None:
                dom = []
                self.domains[domName] = dom
            if not params[i] in dom:
                dom.append(params[i])
        self.evidence[atomString] = truth
                
    def isHard(self):
        '''
        Determines whether or not this database contains exclusively
        hard evidences.
        '''
        return any(map(lambda x: x != 1 and x != 0, self.evidence))
    
                
    def writeToFile(self, filename):
        '''
        Writes this database into the file with the given filename.
        '''
        f = open(filename, 'w+')
        self.write(f)
        f.close()
                
    def write(self, stream, color=False):
        '''
        Writes this database into the stream in the MLN Database format.
        The stream must provide a write() method as file objects do.
        '''
        for atom in sorted(self.evidence):
            truth = self.evidence[atom]
            pred, params = self.mln.logic.parseAtom(atom)
            pred = str(pred)
            params = map(str, params)
            if color:
                strout = '%s  %s\n' % (colorize('%.2f' % truth, (None, 'magenta', False), True), FirstOrderLogic.Lit(False, pred, params).cstr(color))
            else:
                strout = '%s  %s\n' % ('%.2f' % truth, FirstOrderLogic.Lit(False, pred, params).cstr(color))
            stream.write(strout)

    def printEvidence(self):
        for atom, truth in sorted(self.evidence.iteritems()):
            print '%.2f   %s' % (truth, atom)
                
    def retractGndAtom(self, gndLit):
        '''
        Removes the evidence of the given ground atom in this database.
        '''
        if type(gndLit) is str:
            _, predName, params = self.mln.logic.parseLiteral(gndLit)
            atomString = "%s(%s)" % (predName, ",".join(params))
        elif isinstance(gndLit, Logic.GroundLit):
            atomString = str(gndLit.gndAtom)
        else:
            raise Exception('gndLit has an illegal type: %s' % str(type(gndLit)))
        del self.evidence[atomString]
                
    def isEmpty(self):
        '''
        Returns True iff there is an assertion for any ground atom in this
        database and False if the truth values all ground atoms are None
        AND all domains are empty.
        '''
        return not any(map(lambda x: x >= 0 and x <= 1,  self.evidence.values())) and \
            len(self.domains) == 0
                
    def query(self, formula, truthThreshold=1):
        '''
        Makes to the database a 'prolog-like' query given by the specified formula.
        Returns a dictionary with variable-value assignments for which the formula has
        a truth value of at least `truthThreshold`.
        
        ..  warning:: 
            This is _very_ inefficient, since all groundings are gonna be instantiated; so keep the queries short ;)
        
        ''' 
        pseudoMRF = Database.PseudoMRF(self)
        formula = self.mln.logic.parseFormula(formula)
        for varAssignment in pseudoMRF.iterTrueVariableAssignments(formula, truthThreshold=truthThreshold):
            yield varAssignment


    @staticmethod
    def writeDBs(dbs, stream, color=False):
        strdbs = []
        for db in dbs:
            s = StringIO()
            db.write(s, color=color)
            strdbs.append(s.getvalue())
            s.close()
        stream.write('---\n'.join(strdbs))
                        
#     def getSoftEvidence(self, gndAtom):
#         '''
#         gets the soft evidence value (probability) for a given ground atom (or complex formula)
#         returns None if there is no such value
#         '''
#         s = strFormula(gndAtom)
#         for se in self.softEvidence: # TODO optimize
#             if se["expr"] == s:
#                 return se["p"]
#         return None
    
    def getPseudoMRF(self):
        '''
        gets a pseudo-MRF object that can be used to generate formula groundings
        or count true groundings based on the domain in this database
        '''       
        return Database.PseudoMRF(self)

    class PseudoMRF(object):
        '''
        can be used in order to use only a Database object to ground formulas
        (without instantiating an MRF) and determine the truth of these ground
        formulas by partly replicating the interface of an MRF object
        '''
        
        def __init__(self, db):
            self.mln = db.mln
            self.domains = mergeDomains(self.mln.domains, db.domains)
            self.gndAtoms = Database.PseudoMRF.GroundAtomGen()
            # duplicate the database to avoid side effects
            self.evidence = Database.PseudoMRF.WorldValues(db.duplicate())

        class GroundAtomGen(object):
            def __getitem__(self, gndAtomName):
                return Database.PseudoMRF.TextGroundAtom(gndAtomName)
            
            def get(self, key, default=None):
                return self[key]
        
        class TextGroundAtom(object):
            def __init__(self, name):
                self.name = self.idx = name
        
            def isTrue(self, world_values):
                return world_values[self.name]
        
            def __str__(self):
                return self.name
            
            def simplify(self, mrf):
                return self
            
        class WorldValues(object):
            def __init__(self, db):
                self.db = db
            
            def __getitem__(self, gndAtomString):
                return self.db.evidence.get(gndAtomString, 0)
            
        def iterGroundings(self, formula):
            for t in formula.iterGroundings(self):
                yield t
        
        def isTrue(self, gndFormula):
            return gndFormula.isTrue(self.evidence)
        
        def countTrueGroundings(self, formula):
            numTotal = 0
            numTrue = 0
            for gf, _ in self.iterGroundings(formula):
                numTotal += 1
                numTrue += gf.isTrue(self.evidence)
            return (numTrue, numTotal)
        
        def iterTrueVariableAssignments(self, formula, truthThreshold=1.0):
            '''
            Iterates over all groundings of formula that evaluate to true
            given this Pseudo-MRF.
            '''
#             evidence = self.evidence.copy()
            for assignment in formula.iterTrueVariableAssignments(self, self.evidence, truthThreshold=truthThreshold):
                yield assignment
                

def readDBFromString(mln, dbtext, ignoreUnknownPredicates=False, filename=''):
    '''
    Reads one or more databases in a string representation and returns
    the respective Database objects.
    - mln:         the MLN object which should be used to load the database.
    - dbtext:      the string representation of one or multiple ('---'-separated)
                   databases
    '''
    log = logging.getLogger('db')
    dbtext = stripComments(dbtext)
    db = Database(mln)
    dbs = []
    # expand domains with dbtext constants and save evidence
    for l in dbtext.split("\n"):
        l = l.strip()
        if l == '':
            continue
        # separator between independent databases
        elif l == '---' and not db.isEmpty():
            dbs.append(db)
            db = Database(mln)
            continue
        # domain declaration
        elif "{" in l:
            domName, constants = db.mln.logic.parseDomDecl(l)
            domNames = [domName for _ in constants]
        # valued evidence
        elif l[0] in "0123456789":
            s = l.find(" ")
            gndAtom = l[s + 1:].replace(" ", "")
            value = float(l[:s])
            if value < 0 or value > 1:
                raise Exception('Valued evidence must be in [0,1]') 
#             d = {"expr": gndAtom, "p": float(l[:s])}
#             if db.getSoftEvidence(gndAtom) == None:
#                 db.softEvidence.append(d)
#             else:
            if db.evidence.get(gndAtom, None) != None:
                raise log.exception("Duplicate soft evidence for '%s'" % gndAtom)
            positive, predName, constants =   mln.logic.parseLiteral(gndAtom) # TODO Should we allow soft evidence on non-atoms here? (This assumes atoms)
#             if not positive: value = 1. - value
            if not predName in mln.predicates and ignoreUnknownPredicates:
                log.debug('Predicate "%s" is undefined.' % predName)
                continue
            elif not predName in mln.predicates:
                log.exception('Predicate "%s" is undefined.' % predName)
            domNames = mln.predicates[predName]
            db.addGroundAtom(gndAtom, value)
        # literal
        else:
            if l[0] == "?":
                raise log.exception("Unknown literals not supported (%s)" % l) # this is an Alchemy feature
            isTrue, predName, constants = mln.logic.parseLiteral(l)
            if not predName in mln.predicates and ignoreUnknownPredicates:
                log.debug('Predicate "%s" is undefined.' % predName)
                continue
            elif not predName in mln.predicates:
                raise Exception('Predicate "%s" is undefined.' % predName)
            domNames = mln.predicates[predName]
            # save evidence
            isTrue = 1 if isTrue else 0
            db.addGroundAtom("%s(%s)" % (predName, ",".join(constants)), isTrue)
#             db.evidence["%s(%s)" % (predName, ",".join(constants))] = isTrue

        # expand domains
        if len(domNames) != len(constants):
            raise log.exception("Ground atom %s in database %s has wrong number of parameters" % (l, filename))

        if "{" in l or db.includeNonExplicitDomains:
            for i, c in enumerate(constants):
                dom = db.domains.get(domNames[i], None)
                if dom is None:
                    dom = []
                    db.domains[domNames[i]] = dom
                if not c in dom: dom.append(c)
    if not db.isEmpty(): dbs.append(db)
#     if len(dbs) == 1: return db
    return dbs


def readDBFromFile(mln, dbfile, ignoreUnknownPredicates=False):
    '''
    Reads one or multiple database files containing literals and/or domains.
    Returns one or multiple databases where domains is dictionary mapping 
    domain names to lists of constants defined in the database
    and evidence is a dictionary mapping ground atom strings to truth values
    Arguments:
      - dbfile:  a single one or a list of paths to database file.
      - mln:     the MLN object which should be used to load the database.
    Returns:
      either one single or a list of database objects.
      
    Examples:
      Read an MLN `Database` file:

      >>> mln = MLN()
      >>> db = readDBFromFile(mln, './example.db')
    '''
    log = logging.getLogger('db')
    if type(dbfile) is list:
        dbs = []
        for dbpath in dbfile:
            dbobj = readDBFromFile(mln, dbpath)
            if type(dbobj) is list:
                dbs.extend(dbobj)
            else:
                dbs.append(dbobj)
        return dbs
    dbs = []
    # read file
    f = file(dbfile, "r")
    dbtext = f.read()
    f.close()
    return readDBFromString(mln, dbtext, ignoreUnknownPredicates)


def readAllDBsInDir(mln, dbPath):
    '''
    Loads and yields all databases (*.db files) that are located in
    the given directory and returns the corresponding Database objects.
    - dbPath: the directory path to look for .db files
    '''
    for dirname, dirnames, filenames in os.walk(dbPath): #@UnusedVariable
        for f in filenames:
            if not f.endswith('.db'):
                continue
            p = os.path.join(dirname, f)
            print " reading database %s" % p
            dbs = readDBFromFile(mln, p)
            if type(dbs) == list:
                for db in dbs:
                    yield db
            else:
                yield dbs