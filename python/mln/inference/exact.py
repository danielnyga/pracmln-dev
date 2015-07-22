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

from inference import *
from logic.fol import FirstOrderLogic
from praclog import logging
from multiprocessing import Pool
from utils.multicore import with_tracing
from mln.grounding.default import DefaultGroundingFactory
from mln.mrfvars import FuzzyVariable, MutexVariable, SoftMutexVariable
from mln.constants import auto, HARD
from mln.errors import SatisfiabilityException
from mln.grounding.fastconj import FastConjunctionGrounding

# this readonly global is for multiprocessing to exploit copy-on-write
# on linux systems
global_enumAsk = None


def eval_queries(world):
    '''
    Evaluates the queries given a possible world.
    '''
    numerators = [0] * len(global_enumAsk.queries)
    denominator = 0
    expsum = 0
    for gf in global_enumAsk.grounder.itergroundings(simplify=True):
        if global_enumAsk.soft_evidence_formula(gf):                
            expsum += gf.noisyor(world) * gf.weight
        else:
            truth = gf(world)
            if gf.weight == HARD and truth in Interval(']0,1['):
                raise Exception('No real-valued degrees of truth are allowed in hard constraints.')
            if gf.weight == HARD and truth != 1:
                continue #  
            expsum += gf(world) * gf.weight
    expsum = exp(expsum)
    # update numerators
    for i, query in enumerate(global_enumAsk.queries):
        if query(world):
            numerators[i] += expsum
    denominator += expsum
    return numerators, denominator


class EnumerationAsk(Inference):
    '''
    Inference based on enumeration of (only) the worlds compatible with the evidence;
    supports soft evidence (assuming independence)
    '''
    
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)
        self.grounder = FastConjunctionGrounding(mrf, formulas=mrf.formulas, cache=auto, verbose=False, multicore=self.multicore)
#         self.grounder = DefaultGroundingFactory(mrf, formulas=formulas, cache=auto, verbose=False)
        # check consistency of fuzzy and functional variables
        for variable in self.mrf.variables:
            variable.consistent(self.mrf.evidence, strict=isinstance(variable, FuzzyVariable))
        

    def _run(self):
        '''
        verbose: whether to print results (or anything at all, in fact)
        details: (given that verbose is true) whether to output additional status information
        debug: (given that verbose is true) if true, outputs debug information, in particular the distribution over possible worlds
        debugLevel: level of detail for debug mode
        '''
        logger = logging.getLogger(self.__class__.__name__)
        # compute number of possible worlds
        worlds = 1
        for variable in self.mrf.variables:
            values = variable.valuecount(self.mrf.evidence_dicti())
            worlds *= values
        numerators = [0.0 for i in range(len(self.queries))]
        denominator = 0.
        # start summing
        logger.debug("Summing over %d possible worlds..." % worlds)
        k = 0
        self._watch.tag('enumerating worlds', verbose=self.verbose)
        global global_enumAsk
        global_enumAsk = self
        bar = None
        if self.verbose:
            bar = ProgressBar(width=100, steps=worlds, color='green')
        if self.multicore: 
            pool = Pool()
            logger.debug('Using multiprocessing on %d core(s)...' % pool._processes)
            for num, denum in pool.imap(with_tracing(eval_queries), self.mrf.worlds()):
                denominator += denum
                k += 1
                for i, v in enumerate(num):
                    numerators[i] += v
                if self.verbose: bar.inc()
            pool.terminate()
            pool.join()
        else: # do it single core
            for world in self.mrf.worlds():
                # compute exp. sum of weights for this world
                num, denom = eval_queries(world)
                denominator += denom
                for i, _ in enumerate(self.queries):
                    numerators[i] += num[i]
                k += 1
                if self.verbose: bar.update(float(k) / worlds)
        logger.debug("%d worlds enumerated" % k)
        self._watch.finish('enumerating worlds')
        self._watch.tags['grounding'] = self.grounder.watch['grounding']
        if denominator == 0:
            raise SatisfiabilityException('MLN is unsatisfiable. All probability masses returned 0.')
        # normalize answers
        dist = map(lambda x: float(x) / denominator, numerators)
        result = {}
        for q, p in zip(self.queries, dist):
            result[str(q)] = p
        return result
    
    
    def soft_evidence_formula(self, gf):
        return isinstance(self.mrf.mln.logic, FirstOrderLogic) and any(map(lambda a: a.truth(self.mrf.evidence) in Interval('(0,1)'), gf.gndatoms()))
    
    
