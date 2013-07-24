# Weighted Constraint Satisfaction Problems -- MPE inference on MLNs
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

from MLN.inference.Inference import Inference
from wcsp.converter import WCSPConverter
from MLN.util import strFormula

class WCSPInference(Inference):
    
    def __init__(self, mln):
        Inference.__init__(self, mln)
        
    def _infer(self, verbose, details, **args):
        converter = WCSPConverter(self.mrf)
        result = converter.getMostProbableWorldDB(verbose).evidence
        strQueries = map(strFormula, self.queries)
        result = dict([(i, 1. if result[q] == True else 0.) for i, q in enumerate(strQueries)])
        print result
        return result
        