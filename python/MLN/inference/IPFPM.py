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

from Inference import Inference
from MLN.methods import *
from logic.grammar import parseFormula

class IPFPM(Inference):
    ''' the iterative proportional fitting procedure applied at the model level (IPFP-M) '''
    
    def __init__(self, mrf):
        # check if there's any soft evidence to actually work on
        if len(mrf.softEvidence) == 0:
            raise Exception("Application of IPFP-M inappropriate! IPFP-M is a wrapper method for other inference algorithms that allows to fit probability constraints. An application is not sensical if the model contains no such constraints.")
        Inference.__init__(self, mrf)
    
    def _infer(self, verbose=True, details=False, fittingMethod=InferenceMethods.Exact, fittingThreshold=1e-3, fittingSteps=100, fittingParams=None, maxThreshold=None, greedy=False, **args):
        # add formulas to the model whose weights we can then fit
        if verbose: print "extending model with %d formulas whose weights will be fit..." % len(self.mrf.softEvidence)
        for req in self.mrf.softEvidence:            
            formula = parseFormula(req["expr"])
            idxFormula = self.mrf._addFormula(formula, 0.0)                        
            gndFormula = formula.ground(self.mrf, {})
            self.mrf._addGroundFormula(gndFormula, idxFormula)
            req["gndExpr"] = req["expr"]
            req["gndFormula"] = gndFormula
            req["idxFormula"] = idxFormula     

        # do fitting
        if fittingParams is None: fittingParams = {}
        fittingParams.update(args)
        results, self.data = self.mrf._fitProbabilityConstraints(self.mrf.softEvidence, fittingMethod=fittingMethod, fittingThreshold=fittingThreshold, fittingSteps=fittingSteps, given=self.given, queries=self.queries, verbose=details, fittingParams=fittingParams, maxThreshold=maxThreshold, greedy=greedy)
        
        return results
