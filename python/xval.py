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
from mln.util import strFormula, mergeDomains, parseLiteral
from multiprocessing import Pool
import time
import os
import sys
from utils.clustering import SAHN, Cluster, computeClosestCluster

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
parser.add_option('-n', '--noisy', dest='noisy', type='str', default=None,
                  help='-nDOMAIN defines DOMAIN as a noisy string.')

class NoisyStringTransformer(object):
    
    def __init__(self, mln, noisyStringDomains, verbose=False):
        self.mln = mln
        self.noisyStringDomains = noisyStringDomains
        self.verbose = verbose
        self.clusters = {} # maps domain name -> list of clusters
        self.noisyDomains = {}
    
    def materializeNoisyDomains(self, dbs):
        '''
        For each noisy domain, (1) if there is a static domain specification,
        map the values of that domain in all dbs to their closest neighbor
        in the domain.
        (2) If there is no static domain declaration, apply SAHN clustering
        to the values appearing dbs, take the cluster centroids as the values
        of the domain and map the dbs as in (1).
        '''
        fullDomains = mergeDomains(*[db.domains for db in dbs])
        if self.verbose and len(self.noisyStringDomains) > 0:
            print 'materializing noisy domains...'
        for nDomain in self.noisyStringDomains:
            if fullDomains.get(nDomain, None) is None: continue
            # apply the clustering step
            values = fullDomains[nDomain]
            clusters = SAHN(values)
            self.clusters[nDomain] = clusters
            self.noisyDomains[nDomain] = [c._computeCentroid()[0] for c in clusters]
            if self.verbose:
                print '  reducing domain %s: %d -> %d values' % (nDomain, len(values), len(clusters))
                print '   ', self.noisyDomains[nDomain] 
        return self.transformDBs(dbs)
        
    def transformDBs(self, dbs):
        newDBs = []
        for db in dbs:
            if len(db.softEvidence) > 0:
                raise Exception('This is not yet implemented for soft evidence.')
            commonDoms = set(db.domains.keys()).intersection(set(self.noisyStringDomains))
            if len(commonDoms) == 0:
                newDBs.append(db)
                continue
            newDB = db.duplicate()
            for domain in commonDoms:
                # map the values in the database to the static domain values
                valueMap = dict([(val, computeClosestCluster(val, self.clusters[domain])[1][0]) for val in newDB.domains[domain]])
                newDB.domains[domain] = valueMap.values()
                # replace the affected evidences
                for ev in newDB.evidence.keys():
                    truth = newDB.evidence[ev]
                    _, pred, params = parseLiteral(ev)
                    if domain in self.mln.predicates[pred]: # domain is affected by the mapping  
                        newDB.retractGndAtom(ev)
                        newArgs = [v if domain != self.mln.predicates[pred][i] else valueMap[v] for i, v in enumerate(params)]
                        atom = '%s%s(%s)' % ('' if truth else '!', pred, ','.join(newArgs))
                        newDB.addGroundAtom(atom)
            newDBs.append(newDB)
        return newDBs
    
def evalMLN(mln, queryPred, queryDom, cwPreds, dbs, confMatrix):
    
    mln.setClosedWorldPred(None)
    for pred in [pred for pred in cwPreds if pred in mln.predicates]:
        mln.setClosedWorldPred(pred)
    sig = ['?arg%d' % i for i, _ in enumerate(mln.predicates[queryPred])]
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
        db.printEvidence()
        
        mln.defaultInferenceMethod = InferenceMethods.WCSP
        mrf = mln.groundMRF(db)
        conv = WCSPConverter(mrf)
        
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

def learnAndEval(mln, learnDBs, testDBs, queryPred, queryDom, cwPreds, confMatrix, noisyDoms):
    nTransf = NoisyStringTransformer(mln, noisyDoms, True)
    learnDBs_ = nTransf.materializeNoisyDomains(learnDBs)
    testDBs_ = nTransf.transformDBs(testDBs)
    
    learnedMLN = mln.learnWeights(learnDBs_, method=ParameterLearningMeasures.BPLL_CG, optimizer='cg', verbose=verbose, initWeights=True)
    evalMLN(learnedMLN, queryPred, queryDom, cwPreds, testDBs_, confMatrix)
    

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
        learnAndEval(mln_, trainDBs, testDBs, predName, domain, cwpreds, confMatrix, noisyDoms=['text'])
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
    noisy = options.noisy
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
    
    cwpreds = [pred for pred in mln_.predicates if pred != predName]
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
        workerPool = Pool()
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
        
        

    
    
        
    
    
    
    
    