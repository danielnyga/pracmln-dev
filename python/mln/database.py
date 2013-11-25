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

from mln.util import stripComments, parsePredicate, parseDomDecl, parseLiteral,\
    strFormula, mergeDomains
from logic.grammar import parseFormula
from logic.fol import GroundLit
import copy
import logging

class Database(object):
    '''
    Represents an MLN Database, which is a set of ground literals (i.e. ground
    atoms or negated ground atoms)
    Members:
    - mln:        the respective MLN object that this Database is associated to
    - domains:    the variable domain specific to this data base (i.e. without
                  values from the MLN domains which are not present in the DB.
    - evidence    dictionary mapping ground atom strings to truth values
    '''
    
    def __init__(self, mln):
        self.mln = mln
        self.domains = {}
        self.evidence = {}
        self.softEvidence = []
        self.includeNonExplicitDomains = True
        
    def duplicate(self):
        '''
        Returns a deep copy this Database.
        '''
        db = Database(self.mln)
        db.domains = copy.deepcopy(self.domains)
        db.evidence = copy.deepcopy(self.evidence)
        db.softEvidence = copy.deepcopy(self.softEvidence)
        return db

    def iterGroundLiteralStrings(self, pred_names=None):
        '''
        Iterates over all ground literals in this database that match any of
        the given predicate names. If no predicate is specified, it
        yields all ground literals.
        '''
        for atom, truth in self.evidence.iteritems():
            if pred_names is not None:
                _, predName, _ = parseLiteral(atom)
                if not predName in pred_names:
                    continue
            yield '%s%s' % ('' if truth else '!', atom)

    def addGroundAtom(self, gndLit, truth=1):
        '''
        Adds the fact represented by the ground atom, which might be
        a GroundLit object or a string.
        '''
        if type(gndLit) is str:
            isTrue, predName, params = parseLiteral(gndLit)
            atomString = "%s(%s)" % (predName, ",".join(params))
        elif isinstance(gndLit, GroundLit):
            atomString = gndLit.gndAtom
            isTrue = not gndLit.negated
            params = gndLit.params
            predName = gndLit.predName
        else:
            raise Exception('gndLit has an illegal type')
        truth = truth if isTrue else 1 - truth
        self.evidence[atomString] = truth
        # update the domains
        domNames = self.mln.predicates[predName]
        for i, domName in enumerate(domNames):
            dom = self.domains.get(domName, None)
            if dom is None:
                dom = []
                self.domains[domName] = dom
            if not params[i] in dom:
                dom.append(params[i])
                
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
                
    def write(self, stream):
        '''
        Writes this database into the stream in the MLN Database format.
        The stream must provide a write() method as file objects do.
        '''
        for atom, truth in self.evidence.iteritems():
            stream.write('%s%s\n' % ('' if truth else '!', atom))

    def printEvidence(self):
        for atom, truth in sorted(self.evidence.iteritems()):
            print atom, ':', truth
                
    def retractGndAtom(self, gndLit):
        '''
        Removes the evidence of the given ground atom in this database.
        '''
        if type(gndLit) is str:
            _, predName, params = parseLiteral(gndLit)
            atomString = "%s(%s)" % (predName, ",".join(params))
        elif isinstance(gndLit, GroundLit):
            atomString = gndLit.gndAtom
        else:
            raise Exception('gndLit has an illegal type')
        del self.evidence[atomString]
                
    def isEmpty(self):
        '''
        Returns True iff there is an assertion for any ground atom in this
        database and False if the truth values all ground atoms are None
        AND all domains are empty.
        '''
        return not any(map(lambda x: x >= 0 and x <= 1,  self.evidence.values())) and \
            len(self.domains) == 0
                
    def query(self, formula):
        '''
        Makes to the database a 'prolog-like' query given by the specified formula.
        Returns a dictionary with variable-value assignments for which the formula is true.
        Note: this is _very_ inefficient, since all groundings are gonna be
            instantiated; so keep the queries short ;)
        ''' 
        pseudoMRF = Database.PseudoMRF(self)
        formula = parseFormula(formula)
        for varAssignment in pseudoMRF.iterTrueVariableAssignments(formula):
            yield varAssignment
                        
    def getSoftEvidence(self, gndAtom):
        '''
        gets the soft evidence value (probability) for a given ground atom (or complex formula)
        returns None if there is no such value
        '''
        s = strFormula(gndAtom)
        for se in self.softEvidence: # TODO optimize
            if se["expr"] == s:
                return se["p"]
        return None
    
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
            self.evidence = Database.PseudoMRF.WorldValues(db)

        class GroundAtomGen(object):
            def __getitem__(self, gndAtomName):
                return Database.PseudoMRF.TextGroundAtom(gndAtomName)
        
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
        
        def iterTrueVariableAssignments(self, formula):
            '''
            Iterates over all groundings of formula that evaluate to true
            given this Pseudo-MRF.
            '''
            for assignment in formula.iterTrueVariableAssignments(self, self.evidence):
                yield assignment
                
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
    dbtext = stripComments(dbtext)
    db = Database(mln)
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
            domName, constants = parseDomDecl(l)
            domNames = [domName for _ in constants]
        # valued evidence
        elif l[0] in "0123456789":
            s = l.find(" ")
            gndAtom = l[s + 1:].replace(" ", "")
            value = float(l[:s])
            d = {"expr": gndAtom, "p": float(l[:s])}
            if db.getSoftEvidence(gndAtom) == None:
                db.softEvidence.append(d)
            else:
                raise log.exception("Duplicate soft evidence for '%s'" % gndAtom)
            predName, constants = parsePredicate(gndAtom) # TODO Should we allow soft evidence on non-atoms here? (This assumes atoms)
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
            isTrue, predName, constants = parseLiteral(l)
            if not predName in mln.predicates and ignoreUnknownPredicates:
                log.debug('Predicate "%s" is undefined.' % predName)
                continue
            elif not predName in mln.predicates:
                log.exception('Predicate "%s" is undefined.' % predName)
            domNames = mln.predicates[predName]
            # save evidence
            isTrue = 1 if isTrue else 0
            db.addGroundAtom("%s(%s)" % (predName, ",".join(constants)), isTrue)
#             db.evidence["%s(%s)" % (predName, ",".join(constants))] = isTrue

        # expand domains
        if len(domNames) != len(constants):
            raise log.exception("Ground atom %s in database %s has wrong number of parameters" % (l, dbfile))

        if "{" in l or db.includeNonExplicitDomains:
            for i, c in enumerate(constants):
                dom = db.domains.get(domNames[i], None)
                if dom is None:
                    dom = []
                    db.domains[domNames[i]] = dom
                if not c in dom: dom.append(c)
    if not db.isEmpty(): dbs.append(db)
    if len(dbs) == 1: return db
    return dbs
