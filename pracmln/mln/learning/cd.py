# MARKOV LOGIC NETWORKS -- CONTRASTIVE DIVERGENCE LEARNING
#
# (C) 2011-2014 by Daniel Nyga (nyga@cs.uni-bremen.de)
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

from pracmln.mln.learning import AbstractLearner


class CD(AbstractLearner):
    """
    Log-likelihood learning with Contrastive Divergence (CD) approximation.
    """
    
    def __init__(self, mln, mrf, cdSamples=5, **params):
        AbstractLearner.__init__(self, mln, mrf)
        self.cdSamples = cdSamples
    
    def _prepareOpt(self):
        # TODO: count the number of true groundings here
        pass
    
    def _grad(self, wt):
        self.evidence_backup = list(self.mrf.evidence)
        
    def useF(self):
        return False
    
    