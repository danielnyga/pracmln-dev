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

from MLN.util import stripComments, parsePredicate, parseDomDecl, parseLiteral,\
    strFormula, mergeDomains
from logic.grammar import parseFormula
from logic.FOL import GroundLit

class Database(object):
    '''
    Represents an MLN Database, which is a set of ground literals (i.e. ground
    atoms or negated ground atoms)
    '''
    
    def __init__(self, mln):
        self.mln = mln
        self.domains = {}
        self.evidence = {}
        self.softEvidence = []
        self.includeNonExplicitDomains = True
                            
    def addGroundAtom(self, gndLit):
        '''
        Adds the fact represented by the ground atom, which might be
        a GroundLit object or a string. The domains in the associated MLN 
        instance are updated accordingly, if necessary. 
        '''
        if type(gndLit) is str:
            f = parseLiteral(gndLit)
            predName = f.predName
            params = f.params
            isTrue = not f.negated
            atomString = "%s(%s)" % (predName, ",".join(params))
        elif isinstance(gndLit, GroundLit):
            atomString = gndLit.gndAtom
            isTrue = not gndLit.negated
        else:
            raise Exception('gndLit has an illegal type')
        self.evidence[atomString] = isTrue
        domNames = self.mln.predicates[predName]
        for i, v in enumerate(params):
            if domNames[i] not in self.domains:
                self.domains[domNames[i]] = []
            d = self.domains[domNames[i]]
            if v not in d:
                d.append(v)
                
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
                return self.db.evidence.get(gndAtomString, False)
            
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
                if gf.isTrue(self.evidence):
                    numTrue += 1
            return (numTrue, numTotal)
        
        def iterTrueVariableAssignments(self, formula):
            '''
            Iterates over all groundings of formula that evaluate to true
            given this Pseudo-MRF.
            '''
            for assignment in formula.iterTrueVariableAssignments(self, self.evidence):
                yield assignment
                
def readDBFromFile(self, dbfile, mln):
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
    if type(dbfile) is list:
        dbs = []
        for dbpath in dbfile:
            dbobj = readDBFromFile(dbpath, mln)
            if type(dbobj) is list:
                dbs.extend(dbobj)
            else:
                dbs.append(dbobj)
        return dbs
    dbs = []
    domains = self.domains
    # read file
    f = file(dbfile, "r")
    dbtext = f.read()
    f.close()
    dbtext = stripComments(dbtext)
    db = Database(mln)
    dbs.append(db)
    # expand domains with dbtext constants and save evidence
    evidence = db.evidence
    for l in dbtext.split("\n"):
        l = l.strip()
        if l == "":
            continue
        # separator between independent databases
        if l == '---':
            db = Database(mln)
            dbs.append(db)        
        # soft evidence
        if l[0] in "0123456789":
            s = l.find(" ")
            gndAtom = l[s + 1:].replace(" ", "")
            d = {"expr": gndAtom, "p": float(l[:s])}
            if db.getSoftEvidence(gndAtom) == None:
                db.softEvidence.append(d)
            else:
                raise Exception("Duplicate soft evidence for '%s'" % gndAtom)
            predName, constants = parsePredicate(gndAtom) # TODO Should we allow soft evidence on non-atoms here? (This assumes atoms)
            domNames = db.mln.predicates[predName]
        # domain declaration
        elif "{" in l:
            domName, constants = parseDomDecl(l)
            domNames = [domName for _ in constants]
        # literal
        else:
            if l[0] == "?":
                raise Exception("Unknown literals not supported (%s)" % l) # this is an Alchemy feature
            isTrue, predName, constants = parseLiteral(l)
            domNames = mln.predicates[predName]
            # save evidence
            evidence["%s(%s)" % (predName, ",".join(constants))] = isTrue

        # expand domains
        if len(domNames) != len(constants):
            raise Exception("Ground atom %s in database %s has wrong number of parameters" % (l, dbfile))

        if "{" in l or db.includeNonExplicitDomains:
            for i in range(len(constants)):
                if domNames[i] not in domains:
                    domains[domNames[i]] = []
                d = domains[domNames[i]]
                if constants[i] not in d:
                    d.append(constants[i])
    if len(dbs) == 1: return db
    return dbs
