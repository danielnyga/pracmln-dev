# -*- coding: iso-8859-1 -*-
#
# Markov Logic Networks
#
# (C) 2006-2010 by Dominik Jain (jain@cs.tum.edu)
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

from mln.util import *
import mln
import optimize
from mln.methods import LearningMethods
from multiprocessing import Array, Value
import multiprocessing
from multiprocessing import Process
from multiprocessing.synchronize import Lock
from utils import dict_union
import logging
try:
    import numpy
except:
    pass

class AbstractLearner(object):
    
    groundingMethod = 'DefaultGroundingFactory'
    
    __init__params = {'verbose': False,
                      'initialWts': True,
                      'gaussianPriorSigma': None}
    
    def __init__(self, mln, mrf=None, **params):
        # params overrides __init__params
        self.params = dict_union(AbstractLearner.__init__params, params)
        for key, value in self.params.iteritems():
            setattr(self, key, value)
        self.mln = mln
        self.mrf = mrf
        self.params = params
        self.closedWorldAssumption = True
    
    def _reconstructFullWeightVectorWithFixedWeights(self, wt):        
        if len(self._fixedWeightFormulas) == 0:
            return wt
        
        wtD = numpy.zeros(len(self.mln.formulas), numpy.float64)
        wtIndex = 0
        for i, formula in enumerate(self.mln.formulas):
            if (i in self._fixedWeightFormulas):
                wtD[i] = self._fixedWeightFormulas[i]
                #print "self._fixedWeightFormulas[i]", self._fixedWeightFormulas[i]
            else:
                wtD[i] = wt[wtIndex]
                #print "wt[wtIndex]", wt[wtIndex]
                wtIndex = wtIndex + 1
        return wtD
    
    def _projectVectorToNonFixedWeightIndices(self, wt):
        if len(self._fixedWeightFormulas) == 0:
            return wt

        wtD = numpy.zeros(len(self.mln.formulas) - len(self._fixedWeightFormulas), numpy.float64)
        #wtD = numpy.array([mpmath.mpf(0) for i in xrange(len(self.formulas) - len(self._fixedWeightFormulas.items()))])
        wtIndex = 0
        for i, formula in enumerate(self.mln.formulas):
            if (i in self._fixedWeightFormulas):
                continue
            wtD[wtIndex] = wt[i] #mpmath.mpf(wt[i])
            wtIndex = wtIndex + 1   
        return wtD

    def _getTruthDegreeGivenEvidence(self, gndFormula):
        if self.mrf._isTrueGndFormulaGivenEvidence(gndFormula): return 1.0 
        else: return 0.0
    
    def _fixFormulaWeights(self):
        self._fixedWeightFormulas = {}
        for formula in self.mln.fixedWeightFormulas:
            w = formula.weight
            self._fixedWeightFormulas[formula.idxFormula] = w
            
    # TODO warum einfach f? wo aufgerufen?
    def f(self, wt):
        # compute prior
        prior = 0
        if self.gaussianPriorSigma is not None:
            for weight in wt: # we have to use the log of the prior here
                prior -= 1./(2.*(self.gaussianPriorSigma**2)) * weight**2 #gaussianZeroMean(weight, self.gaussianPriorSigma)
        
        # reconstruct full weight vector
        wt = self._reconstructFullWeightVectorWithFixedWeights(wt)
        wt = self._convertToFloatVector(wt)
        #print "_f: wt = ", wt
        #sys.stdout.flush()
        
        # compute likelihood
        likelihood = self._f(wt)
        sys.stdout.write('  likelihood = %f\r' % likelihood)
        sys.stdout.flush()
        
        return likelihood + prior
        
    
    def _fDummy(self, wt):
        ''' a dummy target function that is used when f is disabled '''
        if not hasattr(self, 'dummyFValue'):
            self.dummyFCount = 0
        self.dummyFCount += 1
        if self.dummyFCount > 150:
            return 0
        print "self.dummyFCount", self.dummyFCount
        
        if not hasattr(self, 'dummyFValue'):
            self.dummyFValue = 0
        if not hasattr(self, 'lastFullGradient'):
            self.dummyFValue = 0
        else:
            self.dummyFValue += sum(abs(self.lastFullGradient))
        print "_f: self.dummyFValue = ", self.dummyFValue
#        if not hasattr(self, 'lastFullGradient'):
#            return 0
#        if not hasattr(self, 'dummyFValue'):
#            self.dummyFValue = 1
#        else:
#            if numpy.any(self.secondlastFullGradient != self.lastFullGradient):
#                self.dummyFValue += 1
#            
#        self.secondlastFullGradient = self.lastFullGradient     
        
        return self.dummyFValue
        
    def grad(self, wt):
        wt = self._reconstructFullWeightVectorWithFixedWeights(wt)
        wt = self._convertToFloatVector(wt)
        
        grad = self._grad(wt)
        #print "_grad: wt = %s\ngrad = %s" % (wt, grad)
        #sys.stdout.flush()

        self.lastFullGradient = grad
        
        # add gaussian prior
        if self.gaussianPriorSigma is not None:
            for i, weight in enumerate(wt):
                grad[i] -= 1./(self.gaussianPriorSigma**2) * weight#gradGaussianZeroMean(weight, self.gaussianPriorSigma)
        
        return self._projectVectorToNonFixedWeightIndices(grad)
    
    #make sure mpmath datatypes aren't propagated in here as they can be very slow compared to native floats
    def _convertToFloatVector(self, wts):
        for wt in wts:
            wt = float(wt)
        return wts

    def run(self, **params):
        '''
        Learn the weights of the MLN given the training data previously 
        loaded 
        
        initialWts: whether to use the MLN's current weights as the starting point for the optimization
        '''
        
        log = logging.getLogger(self.__class__.__name__)
        if not 'scipy' in sys.modules:
            raise Exception("Scipy was not imported! Install numpy and scipy if you want to use weight learning.")
        # initial parameter vector: all zeros or weights from formulas
        wt = numpy.zeros(len(self.mln.formulas), numpy.float64)
        # TODO aus mln einlesen (mlnLearningTool.py und mln.py modifizieren), initialWts kommt dort nur im docstring vor 
        # TODO assert gleiche länge ? 
        if self.initialWts:
            for i in range(len(self.mln.formulas)):
                wt[i] = self.mln.formulas[i].weight
            log.debug('Using initial weight vector: %s' % str(wt))
                
        # precompute fixed formula weights
        self._fixFormulaWeights()
        self.wt = self._projectVectorToNonFixedWeightIndices(wt)
        
        self.params.update(params)
    
        self._prepareOpt()
        self._optimize(**params)
        self._postProcess()
            
        return self.wt
    
    def _prepareOpt(self):
        pass
    
    def _postProcess(self):
        pass
    
    def _optimize(self, optimizer = None, **params):
        imposedOptimizer = self.getAssociatedOptimizerName()
        if imposedOptimizer is not None:
            if optimizer is not None: raise Exception("Cannot override the optimizer for this method with '%s'" % optimizer)
            optimizer = imposedOptimizer
        else:
            if optimizer is None: optimizer = "bfgs"
        
        if optimizer == "directDescent":
            opt = optimize.DirectDescent(self.wt, self, **params)        
        elif optimizer == "diagonalNewton":
            opt = optimize.DiagonalNewton(self.wt, self, **params)  
        elif optimizer in ['ga', 'pso']:
            opt = optimize.PlaydohOpt(optimizer, self.wt, self, **params)      
        else:
            opt = optimize.SciPyOpt(optimizer, self.wt, self, **params)        
        
        wt = opt.run()        
        self.wt = self._reconstructFullWeightVectorWithFixedWeights(wt)
        
        
    def useGrad(self):
        return True
    
    def useF(self):
        return True

    def getAssociatedOptimizerName(self):
        return None

    def hessian(self, wt):
        wt = self._reconstructFullWeightVectorWithFixedWeights(wt)
        wt = self._convertToFloatVector(wt)
        fullHessian = self._hessian(wt)
        return self._projectMatrixToNonFixedWeightIndices(fullHessian)
    
    def _projectMatrixToNonFixedWeightIndices(self, matrix):
        if len(self._fixedWeightFormulas) == 0:
            return matrix

        dim = len(self.mln.formulas) - len(self._fixedWeightFormulas)
        proj = numpy.zeros((dim, dim), numpy.float64)
        i2 = 0
        for i in xrange(len(self.mln.formulas)):
            if (i in self._fixedWeightFormulas):
                continue
            j2 = 0
            for j in xrange(len(self.mln.formulas)):
                if (j in self._fixedWeightFormulas):
                    continue
                proj[i2][j2] = matrix[i][j]
                j2 += 1
            i2 += 1            
        return proj

    def _hessian(self, wt):
        raise Exception("The learner '%s' does not provide a Hessian computation; use another optimizer!" % str(type(self)))
    
    def _f(self, wt):
        raise Exception("The learner '%s' does not provide an objective function computation; use another optimizer!" % str(type(self)))

    def getName(self):
        if self.gaussianPriorSigma is None:
            sigma = 'no prior'
        else:
            sigma = "sigma=%f" % self.gaussianPriorSigma
        return "%s[%s]" % (self.__class__.__name__, sigma)
    

class DiscriminativeLearner(AbstractLearner):
    '''
    Abstract superclass of all discriminative learning algorithms.
    Provides some convenience methods for determining the set of 
    query predicates from the common parameters.
    '''
    
    def _getQueryPreds(self, params):
        '''
        Computes from the set parameters the list of query predicates
        for the discriminative learner. Eitehr the 'queryPreds' or 'evidencePreds'
        parameters must be given, both are lists of predicate names.
        '''
        queryPreds = params.get('queryPreds', [])
        if 'evidencePreds' in params:
            evidencePreds = params['evidencePreds']
            queryPreds.extend([p for p in self.mln.predicates if p not in evidencePreds])
            if not set(queryPreds).isdisjoint(evidencePreds):
                raise Exception('Query predicates and evidence predicates must be disjoint.')
        if len(queryPreds) == 0:
            raise Exception("For discriminative Learning, must provide query predicates by setting keyword argument queryPreds to a list of query predicate names, e.g. queryPreds=[\"classLabel\", \"propertyLabel\"].")        
        return queryPreds
    
    
    def _isQueryPredicate(self, predName):
        return predName in self.queryPreds

    def getName(self):
        return self.__class__.__name__ + "[queryPreds:%s]" % ",".join(self.queryPreds)
    

from softeval import truthDegreeGivenSoftEvidence


class SoftEvidenceLearner(AbstractLearner):

    def __init__(self, mln, **params):
        AbstractLearner.__init__(self,mln, **params)
        

    def _getTruthDegreeGivenEvidence(self, gf, worldValues=None):
        if worldValues is None: worldValues = self.mln.evidence
        return truthDegreeGivenSoftEvidence(gf, worldValues, self.mln)
    
def _mt_f(f, learners, wt):
    for learner in learners:
#         fLock.acquire()
        f.value += learner._f(wt)
#         fLock.release()
    
def _mt_grad(grad, learners, wt):
    for learner in learners:
        g = learner._grad(wt)
#         gradLock.acquire()
        for i, c in enumerate(g):
            grad[i] += c
#         gradLock.release()
        

gradLock = Lock()
fLock = Lock()

class MultipleDatabaseLearner(AbstractLearner):
    '''
    learns from multiple databases using an arbitrary sub-learning method for each database, assuming independence between individual databases
    '''
    
    def __init__(self, mln_, method, dbs, **params):
        '''
        dbs: list of tuples (domain, evidence) as returned by the database reading method
        '''
        AbstractLearner.__init__(self, mln, None, **params)
        self.mln = mln_
        self.dbs = dbs
        self.constructor = LearningMethods.byShortName(method)
        self.params = params
        self.learners = []
        self.useMT = False
        log = logging.getLogger(self.__class__.__name__)
        for i, db in enumerate(self.dbs):
            groundingMethod = eval('mln.learning.%s.groundingMethod' % self.constructor)
            log.info("grounding MRF for database %d/%d using %s..." % (i+1, len(self.dbs), groundingMethod))
            mrf = mln_.groundMRF(db, groundingMethod=groundingMethod, cwAssumption=True, **params)
            learner = eval("mln.learning.%s(mln_, mrf, **params)" % self.constructor)
            self.learners.append(learner)
            learner._prepareOpt()
        if self.useMT:
            numCores = multiprocessing.cpu_count()
            if self.verbose:
                log.info('Setting up multi-core processing for %d cores' % numCores)
            self.multiCoreLearners = []
            learnersPerCore = int(ceil(len(self.learners) / float(numCores)))
            for i in range(numCores):
                self.multiCoreLearners.append(self.learners[i*learnersPerCore:(i+1)*learnersPerCore])
            print self.multiCoreLearners
    
    def getName(self):
        return "MultipleDatabaseLearner[%d*%s]" % (len(self.learners), self.learners[0].getName())
        
    def _f(self, wt):
        if self.useMT:
            f = Value('d', 0.0)
            processes = []
            for l in self.multiCoreLearners:
                processes.append(Process(target=_mt_f, args=(f, l, wt)))
            for p in processes:
                p.start()
            for p in processes:
                p.join()
            return float(str(f.value))
        else:
            likelihood = 0
            for learner in self.learners:
                likelihood += learner._f(wt)
            return likelihood
        
    def _grad(self, wt):
        if self.useMT:
            grad = Array('d', len(self.mln.formulas))
            processes = []
            for l in self.multiCoreLearners:
                processes.append(Process(target=_mt_grad, args=(grad, l, wt)))
            for p in processes:
                p.start()
            for p in processes:
                p.join()
            grad2 = []
            for c in grad[:]:
                grad2.append(float(str(c)))
            return grad2
        grad2 = numpy.zeros(len(self.mln.formulas), numpy.float64)
        for i, learner in enumerate(self.learners):
            grad_i = learner._grad(wt)
            #print "  grad %d: %s" % (i, str(grad_i))
            grad2 += grad_i
        return grad2

    def _hessian(self, wt):
        N = len(self.mln.formulas)
        hessian = numpy.matrix(numpy.zeros((N,N)))
        for learner in self.learners:
            hessian += learner._hessian(wt)
        return hessian

    def _prepareOpt(self):
        pass # _prepareOpt is called for individual learners during construction
    
    def _fixFormulaWeights(self):
        self._fixedWeightFormulas = {}
        for learner in self.learners:
            learner._fixFormulaWeights()
            for i, w in learner._fixedWeightFormulas.iteritems():
                if i not in self._fixedWeightFormulas:
                    self._fixedWeightFormulas[i] = 0.0
                self._fixedWeightFormulas[i] += w / len(self.learners)


class IncrementalLearner(AbstractLearner):
    '''
    learns incrementally from multiple databases without looking forward or preloading all existing domains 
    '''
    
    def __init__(self, mln_, method, dbs, **params):

        #(TODO wirklich domain pro db??)
        '''
        dbs: list of tuples (domain, evidence) as returned by the database reading method 
        '''
        AbstractLearner.__init__(self, mln_, None, **params)
        self.mln = mln_
        self.dbs = dbs
        self.constructor = LearningMethods.byShortName(method)
        #self.params = params
        self.learners = []
        self.useMT = False
        self.closedWorldAssumption = True
        log = logging.getLogger(self.__class__.__name__)

        # TODO  cwAssumption=False 
        for i, db in enumerate(self.dbs):
            groundingMethod = eval('mln.learning.%s.groundingMethod' % self.constructor)
            log.info("grounding MRF for database %d/%d using %s..." % (i+1, len(self.dbs), groundingMethod))
            mrf = mln_.groundMRF(db, groundingMethod=groundingMethod, cwAssumption=True, **params)
            learner = eval("mln.learning.%s(mln_, mrf, **params)" % self.constructor)
            self.learners.append(learner)
            learner._prepareOpt()
        if self.useMT:
            numCores = multiprocessing.cpu_count()
            if self.verbose:
                log.info('Setting up multi-core processing for %d cores' % numCores)
            self.multiCoreLearners = []
            learnersPerCore = int(ceil(len(self.learners) / float(numCores)))
            for i in range(numCores):
                self.multiCoreLearners.append(self.learners[i*learnersPerCore:(i+1)*learnersPerCore])
            print self.multiCoreLearners
    
    def getName(self):
        return "IncrementalLearner[%d*%s]" % (len(self.learners), self.learners[0].getName())
        
    def _f(self, wt):
        if self.useMT:
            f = Value('d', 0.0)
            processes = []
            for l in self.multiCoreLearners:
                processes.append(Process(target=_mt_f, args=(f, l, wt)))
            for p in processes:
                p.start()
            for p in processes:
                p.join()
            return float(str(f.value))
        else:
            likelihood = 0
            for learner in self.learners:
                likelihood += learner._f(wt)
            return likelihood
        
    def _grad(self, wt):
        if self.useMT:
            grad = Array('d', len(self.mln.formulas))
            processes = []
            for l in self.multiCoreLearners:
                processes.append(Process(target=_mt_grad, args=(grad, l, wt)))
            for p in processes:
                p.start()
            for p in processes:
                p.join()
            grad2 = []
            for c in grad[:]:
                grad2.append(float(str(c)))
            return grad2
        grad2 = numpy.zeros(len(self.mln.formulas), numpy.float64)
        for i, learner in enumerate(self.learners):
            grad_i = learner._grad(wt)
            #print "  grad %d: %s" % (i, str(grad_i))
            grad2 += grad_i
        return grad2

    def _hessian(self, wt):
        N = len(self.mln.formulas)
        hessian = numpy.matrix(numpy.zeros((N,N)))
        for learner in self.learners:
            hessian += learner._hessian(wt)
        return hessian

    def _prepareOpt(self):
        pass # _prepareOpt is called for individual learners during construction
    
    # TODO ???
    def _fixFormulaWeights(self):
        self._fixedWeightFormulas = {}
        for learner in self.learners:
            learner._fixFormulaWeights()
            for i, w in learner._fixedWeightFormulas.iteritems():
                if i not in self._fixedWeightFormulas:
                    self._fixedWeightFormulas[i] = 0.0
                self._fixedWeightFormulas[i] += w / len(self.learners)
    
