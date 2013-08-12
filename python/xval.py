# Markov Logic Networks -- Automated Cross-Validation Tool
#
# (C) 2012 by Daniel Nyga (nyga@cs.tum.edu)
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

from optparse import OptionParser
from mln.MarkovLogicNetwork import readMLNFromFile
from mln.database import readDBFromFile, Database
from random import shuffle, sample
import math
from mln.methods import ParameterLearningMeasures, InferenceMethods
from wcsp.converter import WCSPConverter
from utils.eval import ConfusionMatrix
from mln.util import strFormula

usage = '''Usage: %prog [options] <predicate> <domain> <mlnfile> <dbfiles>'''
  
parser = OptionParser(usage=usage)
parser.add_option("-k", "--folds", dest="folds", type='int', default=10,
                  help="Number of folds for k-fold Cross Validation")
parser.add_option("-p", "--percent", dest="percent", type='int', default=100,
                  help="Use only PERCENT% of the data. (default=100)")
parser.add_option("-v", "--verbose", dest="verbose", action='store_true', default=False,
                  help="Verbose mode.")

def evalMLN(mln, queryPred, queryDom, cwPreds, dbs, confMatrix):
    
    mln.setClosedWorldPred(None)
    for pred in [pred for pred in cwPreds if pred in mln.predDecls]:
        mln.setClosedWorldPred(pred)
    sig = ['?arg%d' % i for i, _ in enumerate(mln.predDecls[queryPred])]
    querytempl = '%s(%s)' % (queryPred, ','.join(sig))
    
    for db in dbs:
        # save and remove the query predicates from the evidence
        trueDB = Database(mln)
        for bindings in db.query(querytempl):
            atom = querytempl
            for binding in bindings:
                atom = atom.replace(binding, bindings[binding])
            trueDB.addGroundAtom(atom)
            db.retractGndAtom(atom)
#         db.printEvidence()
        
        mrf = mln.groundMRF(db, method='DefaultGroundingFactory')
#         mrf.printEvidence()
        conv = WCSPConverter(mrf)
        resultDB = conv.getMostProbableWorldDB()
        
        sig2 = list(sig)
        entityIdx = mln.predicates[queryPred].index(queryDom)
        for entity in db.domains[queryDom]:
#             print 'evaluating', entity
            sig2[entityIdx] = entity
            query = '%s(%s)' % (queryPred, ','.join(sig2))
            for truth in trueDB.query(query):
                truth = truth.values().pop()
            for pred in resultDB.query(query):
                pred = pred.values().pop()
            confMatrix.addClassificationResult(pred, truth)
        for e, v in trueDB.evidence.iteritems():
            if v is not None:
                db.addGroundAtom('%s%s' % ('' if v is True else '!', e))
    print confMatrix

def learnAndEval(mln, learnDBs, testDBs, queryPred, queryDom, cwPreds, confMatrix):
#     mln = readMLNFromFile(mlnfile)
    learnedMLN = mln.learnWeights(learnDBs, method=ParameterLearningMeasures.BPLL_CG)
    evalMLN(learnedMLN, queryPred, queryDom, cwPreds, dbs, confMatrix)    
    

if __name__ == '__main__':
    (options, args) = parser.parse_args()
    folds = options.folds
    percent = options.percent
    verbose = options.verbose
    predName = args[0]
    domain = args[1]
    mlnfile = args[2]
    dbfiles = args[3:]
    print options
    print args
    # preparations
    mln_ = readMLNFromFile(mlnfile, verbose=verbose)
    mln_.printFormulas()
    print 'Read MLN %s.' % mlnfile
    dbs = []
    for dbfile in dbfiles:
        db = readDBFromFile(mln_, dbfile)
        if type(db) is list:
            dbs.extend(db)
        else:
            dbs.append(db)
    print 'Read %d databases.' % len(dbs)
    
    cwpreds = [pred for pred in mln_.predDecls if pred != predName]
    # create the partition
    subsetLen = int(math.ceil(len(dbs) * percent / 100.0))
    if subsetLen < len(dbs):
        print 'Using only %d of %d DBs' % (subsetLen, len(dbs))
    dbs = sample(dbs, subsetLen)

    if len(dbs) < folds:
        print 'Cannot do %d-fold cross validation with only %d databases.' % (folds, len(dbs))
        exit(0)
    
    shuffle(dbs)
    partSize = int(math.ceil(len(dbs)/float(folds)))
    partition = []
    for i in range(folds):
        partition.append(dbs[i*partSize:(i+1)*partSize])
    confMatrix = ConfusionMatrix()
    for run in range(folds):
        print 'Run %d of %d...' % (run+1, folds)
        trainDBs = []
        for dbs in [dbs for i,dbs in enumerate(partition) if i != run]:
            trainDBs.extend(dbs)
        
        testDBs = partition[run]

        learnAndEval(mln_, trainDBs, testDBs, predName, domain, cwpreds, confMatrix)
    
    
        
    
    
    
    
    