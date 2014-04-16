
import sys
import logging

from playdoh import *
from numpy import exp, tile, array

try:
    import numpy
    from scipy.optimize import fmin_bfgs, fmin_cg, fmin_ncg, fmin_tnc, fmin_l_bfgs_b, fsolve, fmin_slsqp, fmin, fmin_powell
except:
    sys.stderr.write("Warning: Failed to import SciPy/NumPy (http://www.scipy.org)! Parameter learning with PyMLNs is disabled.\n")


class DirectDescent(object):
    '''
    Naive gradient descent optimization.
    '''    
    
    def __init__(self, wt, problem, gtol=1e-3, maxSteps=100, learningRate=0.1, **params):
        self.problem = problem
        self.wt = wt
        self.gtol = gtol
        self.maxSteps = maxSteps
        self.learningRate = learningRate
    
    def run(self):
        log = logging.getLogger(self.__class__.__name__)
        norm = 1
        alpha = self.learningRate
        step = 1
        log.info('starting optimization with %s... (alpha=%f)' % (self.__class__.__name__, alpha))
        while True:
            grad = self.problem.grad(self.wt)
            norm = numpy.linalg.norm(grad)
            log.info("step %d, norm: %f" % (step, norm))
            log.info('grad = %s' % str(grad))
            log.info('wt = %s' % str(self.wt))
            if norm < self.gtol or step > self.maxSteps:
                break
            step += 1
            self.wt += grad * alpha
        return self.wt


class DiagonalNewton(object):
    
    def __init__(self, wt, problem, gtol=0.01, maxSteps=None):
        self.problem = problem
        self.wt = wt
        self.gtol = gtol
        self.maxSteps = maxSteps
    
    def run(self):
        p = self.problem
        grad_fct = lambda wt: p.grad(wt)
        wt = numpy.matrix(self.wt).transpose()
        wtarray = numpy.asarray(wt.transpose())[0]        
        N = len(wt)
        l = 0.5                
        
        # initial gradient
        g = numpy.asmatrix(grad_fct(wtarray)).transpose()
        d = numpy.sign(g)
        dT = d.transpose()        
        
        step = 1
        while self.maxSteps is None or step <= self.maxSteps:            
            
            # determine convergence
            normg = numpy.linalg.norm(g)
            if normg <= self.gtol:
                print "\nThreshold reached after %d steps. final gradient: %s (norm: %f <= %f)" % (step, g.transpose(), normg, self.gtol)
                break
            
            H = -p.hessian(wtarray)
            
            # scale gradient with inverse diagonal Hessian
            sgrad = numpy.asmatrix(numpy.zeros(N)).transpose()
            for i in xrange(N):
                v = H[i][i]
                if v == 0.0: # HACK: if any variance component is zero, set corresponding gradient component to zero
                    sgrad[i] = g[i] = 0.0
                else:                
                    sgrad[i] = g[i] / v

            # compute predicted change in likelihood
            delta_predict = dT * (g + H * g) / 2.0
    
            alpha_numerator = dT * g
            alpha_q = dT * H * d
            
            while True:
                # determine step coefficient
                alpha = numpy.float(alpha_numerator / (alpha_q + l * dT * d))
    
                # make the step
                wt_old = numpy.matrix(wt)
                wt += alpha * sgrad
                wtarray = numpy.asarray(wt.transpose())[0]                
                
                # compute new gradient
                g = numpy.asmatrix(grad_fct(wtarray)).transpose()
                d = numpy.sign(g)
                dT = d.transpose()
                
                # estimate actual likelihood change
                delta_actual = dT * g

                # update lambda
                frac = delta_actual / delta_predict
                if frac > 0.75 : l /= 2.0 # (lambda may become zero due to precision loss)
                elif frac < 0.25:
                    if l != 0.0: l *= 4.0
                    else: l = 1.0e-5
                
                if delta_actual >= 0: # accept move                    
                    print
                    print "step %d" % step
                    print "H:\n%s" % H
                    print "|g|: %f" % normg
                    print "sgrad: %s" % sgrad.transpose()
                    print "delta_a: %f" % delta_actual
                    print "delta_p: %f" % delta_predict                    
                    print "lambda: %.18f" % l
                    print "alpha: %f" % alpha            
                    print "old wt: %s" % wt_old.transpose()
                    print "new wt: %s" % wt.transpose()
                    break
                else: # reject move
                    print "delta_a=%f, adjusted lambda to %f" % (delta_actual, l)
                    wt = wt_old

            step += 1
        
        return numpy.asarray(wt.transpose())[0]

class FitnessTest(Fitness):
    # This method allows to initialize some data.
    def initialize(self, problem):
        self.problem = problem

    # This method is called at every iteration.
    def evaluate(self, x):
	xt = x.T
	result = []
	for i in range(xt.shape[0]):
        	result.append(self.problem._f(xt[i]))
	return array(result)
	
class PlaydohOpt(object):
	# Maximize the fitness function in parallel
	def __init__(self, problem, wt, machines=["localhost"]):
		self.problem = problem
		self.wt = wt
		self.machines = machines

	def run(self, popSize=10, algorithm=PSO, initRange=[-10,10], maxIter=10):
		initrange = numpy.tile(initRange, (len(self.wt), 1))
		results = maximize(FitnessTest,
			       popsize=popSize,  # size of the population
			       maxiter=maxIter,  # maximum number of iterations
			       cpu=MAXCPU,  # number of CPUs to use on the local machine
			       args=(self.problem,),  # parameters for the "initialize" method
			       initrange=initrange, # initial range for the x parameter
			       machines=self.machines, #list of machines to use
			       algorithm=algorithm) #algorithm to use

		# Display the final result in a table
		print_table(results)
		#print results.best_pos
		return results.best_pos 

class SciPyOpt(object):
    '''
    Wrapper around the optimization techniques implemented by SciPy.
    '''
    
    
    def __init__(self, optimizer, wt, problem, **optParams):
        self.wt = wt
        self.problem = problem        
        self.optParams = optParams
        self.optimizer = optimizer
    
    def run(self):
        optimizer = self.optimizer
        p = self.problem
        f = p.f
        grad = p.grad
        
        # coerce return types
        f = lambda wt: numpy.float64(p.f(wt))
        grad = lambda wt: numpy.array(map(numpy.float64, p.grad(wt)))
        
        # negate for minimization
        neg_f = lambda wt: -f(wt)
        neg_grad = lambda wt: -grad(wt)
        #if not useGrad or not p.useGrad(): neg_grad = None
        if not p.useF(): 
            neg_f = lambda wt: -p._fDummy(wt)
        log = logging.getLogger(self.__class__.__name__)
        if optimizer == "bfgs":
            params = dict(filter(lambda (k,v): k in ["gtol", "epsilon", "maxiter"], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            wt, f_opt, grad_opt, Hopt, func_calls, grad_calls, warn_flags = fmin_bfgs(neg_f, self.wt, fprime=neg_grad, full_output=True, **params)
            log.info("optimization done with %s..." % optimizer)
            log.info("f-opt: %.16f\nfunction evaluations: %d\nwarning flags: %d\n" % (-f_opt, func_calls, warn_flags))
        elif optimizer == "cg":            
            params = dict(filter(lambda (k,v): k in ["gtol", "epsilon", "maxiter"], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            wt, f_opt, func_calls, grad_calls, warn_flags = fmin_cg(neg_f, self.wt, fprime=neg_grad, args=(), full_output=True, **params)
            log.info("optimization done with %s..." % optimizer)
            log.info("f-opt: %.16f\nfunction evaluations: %d\nwarning flags: %d\n" % (-f_opt, func_calls, warn_flags))
        elif optimizer == "ncg":            
            params = dict(filter(lambda (k,v): k in ["avextol", "epsilon", "maxiter"], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            wt, f_opt, func_calls, grad_calls, warn_flags = fmin_ncg(neg_f, self.wt, fprime=neg_grad, args=(), full_output=True, **params)
            log.info("optimization done with %s..." % optimizer)
            log.info("f-opt: %.16f\nfunction evaluations: %d\nwarning flags: %d\n" % (-f_opt, func_calls, warn_flags))
        elif optimizer == "fmin":
            params = dict(filter(lambda (k,v): k in ["xtol", "ftol", "maxiter"], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            wt = fmin(neg_f, self.wt, args=(), full_output=True, **params)
            log.info("optimization done with %s..." % optimizer)
        elif optimizer == "powell":
            params = dict(filter(lambda (k,v): k in ["xtol", "ftol", "maxiter"], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            wt = fmin_powell(neg_f, self.wt, args=(), full_output=True, **params)
            log.info("optimization done with %s..." % optimizer)
        elif optimizer == 'l-bfgs-b':
            params = dict(filter(lambda (k,v): k in ["gtol", "epsilon", "maxiter", 'bounds'], self.optParams.iteritems()))
            log.info("starting optimization with %s... %s" % (optimizer, params))
            if 'bounds' in params:
                params['bounds'] = (params['bounds'],) * len(self.wt)
            wt, f_opt, d = fmin_l_bfgs_b(neg_f, self.wt, fprime=neg_grad, **params)
            log.info("optimization done with %s..." % optimizer)
            log.info("f-opt: %.16f\n" % (-f_opt))
        else:
            raise Exception("Unknown optimizer '%s'" % optimizer)
        
        return wt
