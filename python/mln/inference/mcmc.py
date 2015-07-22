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

import random

import copy

from inference import *
import logging


logger = logging.getLogger(__name__)


class MCMCInference(Inference):
    '''
    Abstract super class for Markov chain Monte Carlo-based inference.
    '''
    
    def random_world(self, evidence=None):
        '''
        Get a random possible world, taking the evidence into account.
        '''
        if evidence is None:
            world = list(self.mrf.evidence)
        else:
            world = list(evidence)
        for var in self.mrf.variables:
            evdict = var.value2dict(var.evidence_value(world))
            valuecount = var.valuecount(evdict)
            if valuecount > 1:
                # get a random value of the variable
                validx = random.randint(0, valuecount - 1)
                value = [v for _, v in var.itervalues(evdict)][validx]
                var.setval(value, world)
        return world
                

    class Chain:
        '''
        Represents the state of a Markov Chain.
        '''
        
        
        def __init__(self, infer, queries):
            self.queries = queries
            self.soft_evidence = None
            self.steps = 0
            self.truth = [0] * len(self.queries)
            self.converged = False
            self.lastresult = 10
            self.infer = infer
            # copy the current  evidence as this chain's state
            self.state = list(infer.mrf.evidence)
            # initialize remaining variables randomly (but consistently)
            self.state = infer.random_world(self.state)
        
        
        def update(self):
            self.steps += 1
            # keep track of counts for queries
            for i in range(len(self.queries)):
                self.truths[i] += self.queries[i](self.state)
            # check if converged !!! TODO check for all queries
            if self.steps % 50 == 0:
                result = self.results()[0]
                diff = abs(result - self.lastresult)
                if diff < 0.001:
                    self.converged = True
                self.lastresult = result
            # keep track of counts for soft evidence
            if self.soft_evidence is not None:
                for se in self.soft_evidence:
                    self.softev_counts[se["expr"]] += se["formula"](self.state)
#                     log.info(self.currentlyTrue(se["formula"]))
            # debug output
#             if True:#self.numSteps % 50 == 0 and debug:
#                 print "  --> %s" % str(self.state), "after %d steps: P(%s | e) = %f" % (self.numSteps, str(self.queries), float(self.numTrue) / self.numSteps)
#                 pass
        
        def set_soft_evidence(self, soft_evidence):
            self.soft_evidence = soft_evidence
            self.softev_counts = {}
            for se in soft_evidence:
                if 'formula' not in se:
                    formula = self.infer.mrf.mln.logic.parse_formula(se['expr'])
                    se['formula'] = formula.ground(self.infer.mrf, {})
                    se['expr'] = fstr(se['formula'])
                self.softev_counts[se["expr"]] = se["formula"](self.state)
        
        
        def soft_evidence_frequency(self, formula):
            if self.steps == 0: return 0
            return float(self.softev_counts[fstr(formula)]) / self.steps
        
        
        def results(self):
            results = []
            for i in range(len(self.queries)):
                results.append(float(self.truths[i]) / self.steps)
            return results
    
            
    class ChainGroup:
        
        def __init__(self, infer):
            self.chains = []
            self.infer = infer
    
    
        def chain(self, chain):
            self.chains.append(chain)
    
    
        def results(self):
            chains = float(len(self.chains))
            queries = self.chains[0].queries
            # compute average
            results = [0.0] * len(queries)
            for chain in self.chains:
                cr = chain.results()
                for i in range(len(queries)):
                    results[i] += cr[i] / chains
            # compute variance
            var = [0.0 for i in range(len(queries))]
            for chain in self.chains:
                cr = chain.results()
                for i in range(len(self.chains[0].queries)):
                    var[i] += (cr[i] - results[i]) ** 2 / chains
            return dict([(q, p) for q, p in zip(self.queries, results)]), var
        
        
        def avgtruth(self, formula):
            ''' returns the fraction of chains in which the given formula is currently true '''
            t = 0.0 
            for c in self.chains:
                t += formula(c.state)
            return t / len(self.chains)
        
        
#         def write(self, short=False):
#             if len(self.chains) > 1:
#                 for i in range(len(self.infer.queries)):
#                     self.infer.additionalQueryInfo[i] = "[%d x %d steps, sd=%.3f]" % (len(self.chains), self.chains[0].steps, sqrt(self.var[i]))
#             self.inferObject._writeResults(sys.stdout, self.results, shortOutput)
