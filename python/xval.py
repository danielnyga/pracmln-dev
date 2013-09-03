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
from multiprocessing import Pool
import time
import os
import sys

usage = '''Usage: %prog [options] <predicate> <domain> <mlnfile> <dbfiles>'''
  
parser = OptionParser(usage=usage)
parser.add_option("-k", "--folds", dest="folds", type='int', default=10,
                  help="Number of folds for k-fold Cross Validation")
parser.add_option("-p", "--percent", dest="percent", type='int', default=100,
                  help="Use only PERCENT% of the data. (default=100)")
parser.add_option("-v", "--verbose", dest="verbose", action='store_true', default=False,
                  help="Verbose mode.")
parser.add_option("-m", "--multicore", dest="multicore", action='store_true', default=False,
                  help="Verbose mode.")

def evalMLN(mln, queryPred, queryDom, cwPreds, dbs, confMatrix):
    
    mln.setClosedWorldPred(None)
    for pred in [pred for pred in cwPreds if pred in mln.predDecls]:
        mln.setClosedWorldPred(pred)
    sig = ['?arg%d' % i for i, _ in enumerate(mln.predDecls[queryPred])]
    querytempl = '%s(%s)' % (queryPred, ','.join(sig))
    
#     f = open('temp.mln', 'w+')
#     mln.write(f)
#     f.close()
    
    for db in dbs:
        # save and remove the query predicates from the evidence
        trueDB = Database(mln)
        for bindings in db.query(querytempl):
            atom = querytempl
            for binding in bindings:
                atom = atom.replace(binding, bindings[binding])
            trueDB.addGroundAtom(atom)
            db.retractGndAtom(atom)
        db.printEvidence()
        
        # for testing purposes
#         mln_ = readMLNFromFile('temp.mln')
#         mln_.setClosedWorldPred(None)
#         for pred in [pred for pred in cwPreds if pred in mln_.predDecls]:
#             mln_.setClosedWorldPred(pred)
#         mrf_ = mln_.groundMRF(db)
#         conv_ = WCSPConverter(mrf_)
#         wcsp_ = conv_.convert()
        
        mln.formulas = None
        mln.defaultInferenceMethod = InferenceMethods.WCSP
        mrf = mln.groundMRF(db)
        conv = WCSPConverter(mrf)
        wcsp = conv.convert()
        
#         if not (wcsp == wcsp_):
#             wcsp.write(sys.stdout)
#             mln.write(sys.stdout)
#             print '+++++++++++++++++++++++++++++++++++'
#             wcsp_.write(sys.stdout)
#             mln_.write(sys.stdout)
#             raise Exception('WCSPs are not equal!!!')
        
#         conv = WCSPConverter(mrf)        
        resultDB = conv.getMostProbableWorldDB()
        
        sig2 = list(sig)
        entityIdx = mln.predicates[queryPred].index(queryDom)
        for entity in db.domains[queryDom]:
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
    if verbose:
        print confMatrix

def learnAndEval(mln, learnDBs, testDBs, queryPred, queryDom, cwPreds, confMatrix):
    learnedMLN = mln.learnWeights(learnDBs, method=ParameterLearningMeasures.BPLL_CG, optimizer='cg', verbose=verbose)
    evalMLN(learnedMLN, queryPred, queryDom, cwPreds, testDBs, confMatrix)
    

# def runFold(mln_, partition, foldIdx, directory):
def runFold(args):
    try:
        foldIdx = args['foldIdx']
        partition = args['partition']
        directory = args['directory']
        mln_ = args['mln_']
        print 'Run %d of %d...' % (foldIdx+1, folds)
        trainDBs = []
        confMatrix = ConfusionMatrix()
        for dbs in [dbs for i,dbs in enumerate(partition) if i != foldIdx]:
            trainDBs.extend(dbs)
        testDBs = partition[foldIdx]
        learnAndEval(mln_, trainDBs, testDBs, predName, domain, cwpreds, confMatrix)
        confMatrix.toFile(os.path.join(directory, 'conf_matrix_%d.cm' % foldIdx))
        return confMatrix
    except (KeyboardInterrupt, SystemExit):
        print "Exiting..."
        return None
    
if __name__ == '__main__':
    (options, args) = parser.parse_args()
    folds = options.folds
    percent = options.percent
    verbose = options.verbose
    multicore = options.multicore
    predName = args[0]
    domain = args[1]
    mlnfile = args[2]
    dbfiles = args[3:]
    
    startTime = time.time()
    directory = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
    print 'Results will be written into %s' % directory

    # preparations
    mln_ = readMLNFromFile(mlnfile, verbose=verbose)
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
    
    os.mkdir(directory)
    
    if multicore:
        # set up a pool of worker processes
        workerPool = Pool(2)
        kwargs = [{'mln_': mln_.duplicate(), 'partition': partition, 'foldIdx': i, 'directory': directory} for i in range(folds)]
        result = workerPool.map_async(runFold, kwargs).get()
        print 'Started %d-fold Crossvalidation in %d processes.' % (folds, workerPool._processes)
        workerPool.close()
        workerPool.join()
        cm = ConfusionMatrix()
        for r in result:
            print r
            cm.combine(r)
        cm.toPDF(os.path.join(directory, 'conf_matrix'))
        elapsedTimeMP = time.time() - startTime
#     startTime = time.time()
    else:
        for fold in range(folds):
            args = {'mln_': mln_.duplicate(), 'partition': partition, 'foldIdx': fold, 'directory': directory}
            runFold(args)
        elapsedTimeSP = time.time() - startTime
    
    if multicore:
        print '%d-fold crossvalidation (MP) took %.2f min' % (folds, elapsedTimeMP / 60.0)
    else:
        print '%d-fold crossvalidation (SP) took %.2f min' % (folds, elapsedTimeSP / 60.0)
        
        

    
    
        
    
    
    
    
    