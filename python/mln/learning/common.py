# -*- coding: utf-8 -*-
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

import optimize
from mln.methods import LearningMethods
from multiprocessing import Array, Value, Pool
import multiprocessing
from multiprocessing import Process
from multiprocessing.synchronize import Lock
import logging
import traceback
import signal
from utils.multicore import with_tracing
import sys
from numpy.ma.core import exp
from mln.util import ProgressBar, StopWatch
import random
import time
from mln.constants import HARD


try:
    import numpy
except:
    pass

logger = logging.getLogger(__name__)


class AbstractLearner(object):
    '''
    Abstract base class for every MLN learning algorithm.
    '''
    
    def __init__(self, mrf=None, **params):
        self.mrf = mrf
        self._params = params
        self.mrf.consistent(strict=True)


    @property
    def prior_stdev(self):
        return self._params.get('prior_stdev')
    

    @property
    def verbose(self):
        return self._params.get('verbose', False)
    
    
    @property
    def use_init_weights(self):
        return self._params.get('use_init_weights')
    

    @property
    def usegrad(self):
        return True
    
    
    @property
    def usef(self):
        return True
    
    
    @property
    def multicore(self):
        return self._params.get('multicore', False)
    
    
    @property
    def weights(self):
        return self._w
    
    
    def _fullweights(self, w):
        i = 0
        w_ = []
        for f in self.mrf.formulas:
            if self.mrf.mln.fixweights[f.idx]:
                w_.append(self._w[f.idx])
            else:
                w_.append(w[i])
                i += 1
        return w_
    
    
    def _varweights(self):
        return self._remove_fixweights(self._w)
    
    
    def f(self, weights):
        # reconstruct full weight vector
        self._w = self._fullweights(weights) 
        # compute prior
        prior = 0
        if self.prior_stdev is not None:
            for w in self._w: # we have to use the log of the prior here
                prior -= 1. / (2. * (self.prior_stdev ** 2)) * w ** 2 
        # compute log likelihood
        likelihood = self._f(self._w)
        if self.verbose:
            sys.stdout.write('                                           \r')
            if self.prior_stdev is not None:
                sys.stdout.write('  log P(D|w) + log P(w) = %f + %f = %f\r' % (likelihood, prior, likelihood + prior))
            else:
                sys.stdout.write('  log P(D|w) = %f\r' % likelihood)
            sys.stdout.flush()
        return likelihood + prior
        
        
    def __call__(self, weights):
        return self.likelihood(weights)
        
        
    def likelihood(self, wt):
        l = self.f(wt)
        l = exp(l)
        return l
    
    
    def _fDummy(self, wt):
        ''' a dummy target function that is used when f is disabled '''
        if not hasattr(self, 'dummy_f'):
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
    
        
    def grad(self, weights):
        self._w = self._fullweights(weights)
        grad = self._grad(self._w)
        self._grad_ = grad
        # add gaussian prior
        if self.prior_stdev is not None:
            for i, weight in enumerate(self._w):
                grad[i] -= 1./(self.prior_stdev ** 2) * weight
        return self._remove_fixweights(grad)

    
    def _remove_fixweights(self, v):
        '''
        Removes from the vector `v` all elements at indices that correspond to a fixed weight formula index.
        '''
        if len(v) != len(self.mrf.formulas):
            raise Exception('Vector must have same length as formula weights')
        v_ = []#numpy.zeros(len(v), numpy.float64)
        for val in [v[i] for i in range(len(self.mrf.formulas)) if not self.mrf.mln.fixweights[i]]:
            v_.append(val)
        return v_
    
    
    def run(self, **params):
        '''
        Learn the weights of the MLN given the training data previously 
        loaded 
        '''
        if not 'scipy' in sys.modules:
            raise Exception("Scipy was not imported! Install numpy and scipy if you want to use weight learning.")
        # initial parameter vector: all zeros or weights from formulas
        self._w = [0] * len(self.mrf.formulas)
        for f in self.mrf.formulas:
            if self.mrf.mln.fixweights[f.idx] or self.use_init_weights:
                self._w[f.idx] = f.weight
        self._prepare()
        self._optimize(**self._params)
        self._cleanup()
        return self.weights
    
    
    def _prepare(self):
        pass

    
    def _cleanup(self):
        pass

    
    def _optimize(self, optimizer='bfgs', **params):
        w = self._varweights()
        if optimizer == "directDescent":
            opt = optimize.DirectDescent(w, self, **params)        
        elif optimizer == "diagonalNewton":
            opt = optimize.DiagonalNewton(w, self, **params)  
        else:
            opt = optimize.SciPyOpt(optimizer, w, self, **params)        
        w = opt.run()
        self._w = self._fullweights(w)
        
        
    def hessian(self, wt):
        wt = self._reconstructFullWeightVectorWithFixedWeights(wt)
        wt = map(float, wt)
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

    
    def _f(self, wt, **params):
        raise Exception("The learner '%s' does not provide an objective function computation; use another optimizer!" % str(type(self)))


    @property
    def name(self):
        if self.prior_stdev is None:
            sigma = 'no prior'
        else:
            sigma = "sigma=%f" % self.prior_stdev
        return "%s[%s]" % (self.__class__.__name__, sigma)
    
    

class DiscriminativeLearner(AbstractLearner):
    '''
    Abstract superclass of all discriminative learning algorithms.
    Provides some convenience methods for determining the set of 
    query predicates from the common parameters.
    '''
    
    
    @property
    def qpreds(self):
        '''
        Computes from the set parameters the list of query predicates
        for the discriminative learner. Eitehr the 'qpreds' or 'epreds'
        parameters must be given, both are lists of predicate names.
        '''
        qpreds = self._params.get('qpreds', [])
        if 'epreds' in self._params:
            epreds = self._params['epreds']
            qpreds.extend([p for p in self.mrf.predicates if p not in epreds])
            if not set(qpreds).isdisjoint(epreds):
                raise Exception('Query predicates and evidence predicates must be disjoint.')
        if len(qpreds) == 0:
            raise Exception("For discriminative Learning, query or evidence predicates must be provided.")        
        return qpreds
    
    
    def _qpred(self, predname):
        return predname in self.qpreds

    
    @property
    def name(self):
        return self.__class__.__name__ + "[queryPreds:%s]" % ",".join(self.qpreds)
    
    
class SoftEvidenceLearner(AbstractLearner):
    '''
    Superclass for all soft-evidence learners.
    '''
    def __init__(self, mrf, **params):
        AbstractLearner.__init__(self, mrf, **params)
        

    def _getTruthDegreeGivenEvidence(self, gf, world=None):
        if world is None: world = self.mrf.evidence
        return gf.noisyor(world)
    


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
        
    def _f(self, wt, **params):
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
        
    def _grad(self, wt, **params):
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
    
