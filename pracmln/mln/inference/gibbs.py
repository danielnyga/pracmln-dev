# -*- coding: iso-8859-1 -*-
#
# Markov Logic Networks
#
# (C) 2006-2011 by Dominik Jain (jain@cs.tum.edu)
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

from pracmln.mln.inference.maxwalk import SAMaxWalkSAT
from pracmln.mln.mrfvars import BinaryVariable
from pracmln.mln.inference.mcmc import MCMCInference
import random


class GibbsSampler(MCMCInference):

    
    class Chain(MCMCInference.Chain):
    
        
        def __init__(self, infer, queries):
            MCMCInference.Chain.__init__(self, infer, queries)            
            self.mws = SAMaxWalkSAT(self.infer.mrf)
            self.mws.run()
    
            
        def _var_expsums(self, var, world):
            sums = [0] * len(var.gndatoms)
            for gf in self.mws.var2gf[var.idx]:
                for i, value in var.itervalues():
                    world_ = list(world)
                    var.setval(value, world_)
                    sums[i] += gf.weight * gf(world)
            return map(math.exp, sums)

        
        def step(self):
            mrf = self.infer.mrf
            # reassign values by sampling from the conditional distributions given the Markov blanket
            for var in self.mrf.variables:
                # compute distribution to sample from
                evdict = var.value2dict(var.evidence_value(self.mrf.evidence))
                valuecount = var.valuecount(evdict) 
                if valuecount == 1: # do not sample if we have evidence 
                    continue  
                expsums = self._var_expsums(var, self.state)
                Z = sum(expsums)
                # check for soft evidence and greedily satisfy it if possible                
                idx = None
                if isinstance(var, BinaryVariable):
                    atoms = var.gndatoms[0]
                    p = mrf.evidence[var.gndatoms[0]]
                    if p is not None:
                        currentBelief = self.getSoftEvidenceFrequency(formula)
                        if p > currentBelief and expsums[1] > 0:
                            idx = 1
                        elif p < currentBelief and expsums[0] > 0:
                            idx = 0
                # sample value
                if idx is None:
                    r = random.uniform(0, Z)                    
                    idx = 0
                    s = expsums[0]
                    while r > s:
                        idx += 1
                        s += expsums[idx]                
                # make assignment
                if block != None:
                    for i, idxGA in enumerate(block):
                        tv = (i == idx)
                        self.state[idxGA] = tv
                    if debug: print "  setting block %s to %s, odds = %s" % (str(map(lambda x: str(mln.gndAtomsByIdx[x]), block)), str(mln.gndAtomsByIdx[block[idx]]), str(expsums))
                else:
                    self.state[idxGA] = bool(idx)
                    if debug: print "  setting atom %s to %s" % (str(mln.gndAtomsByIdx[idxGA]), bool(idx))
            # update results
            self.update()
    
    def __init__(self, mln):
        print "initializing Gibbs sampler...",
        self.useConvergenceTest = False
        MCMCInference.__init__(self, mln)
        # check compatibility with MLN
        for f in mln.formulas:
            if not f.isLogical():
                raise Exception("GibbsSampler does not support non-logical constraints such as '%s'!" % fstr(f))
        # get the pll blocks
        mln._getPllBlocks()
        # get the list of relevant ground atoms for each block
        mln._getBlockRelevantGroundFormulas()
        print "done."

    # infer one or more probabilities P(F1 | F2)
    #   what: a ground formula (string) or a list of ground formulas (list of strings) (F1)
    #   given: a formula as a string (F2)
    def _infer(self, verbose=True, numChains=3, maxSteps=5000, shortOutput=False, details=False, debug=False, debugLevel=1, infoInterval=10, resultsInterval=100, softEvidence=None, **args):
        random.seed(time.time())
        # set evidence according to given conjunction (if any)
        self._readEvidence()
        if softEvidence is None:
            self.softEvidence = self.mln.softEvidence
        else:
            self.softEvidence = softEvidence
        # initialize chains
        if verbose and details:
            print "initializing %d chain(s)..." % numChains
        chainGroup = MCMCInference.ChainGroup(self)
        for i in range(numChains):
            chain = GibbsSampler.Chain(self)
            chainGroup.addChain(chain)
            if self.softEvidence is not None:
                chain.setSoftEvidence(self.softEvidence)
        # do Gibbs sampling
        if verbose and details: print "sampling..."
        converged = 0
        numSteps = 0
        minSteps = 200
        while converged != numChains and numSteps < maxSteps:
            converged = 0
            numSteps += 1
            for chain in chainGroup.chains:
                chain.step(debug=debug)
                if self.useConvergenceTest:
                    if chain.converged and numSteps >= minSteps:
                        converged += 1
            if verbose and details:
                if numSteps % infoInterval == 0:
                    print "step %d (fraction converged: %.2f)" % (numSteps, float(converged) / numChains)
                if numSteps % resultsInterval == 0:
                    chainGroup.getResults()
                    chainGroup.printResults(shortOutput=True)
        # get the results
        return chainGroup.getResults()
