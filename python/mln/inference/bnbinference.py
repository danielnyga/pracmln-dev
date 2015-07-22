# MPE Inference with Branch-&-Bound Search
#
# (C) 2013 by Daniel Nyga (nyga@cs.tum.edu)
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

from mln.inference.inference import Inference
from wcsp.branchandbound import BranchAndBound
from mln.util import fstr
from wcsp.russiandoll import RussianDoll

class BnBInference(Inference):
    
    def __init__(self, mln):
        Inference.__init__(self, mln)

    def _infer(self, verbose, details, **args):
        bnb = RussianDoll(self.mrf)
        bnb.search()
        result = bnb.best_solution
        strQueries = map(fstr, self.queries)
        if result is None:
            raise Exception('Knowledge base is unsatisfiable.')
        result = dict([(i, 1. if result[q] == True else 0.) for i, q in enumerate(strQueries)])
        return result
    