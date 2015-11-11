# Markov Logic Networks -- Russian Doll Search for MPE inference
#
# (C) 2011-2013 by Daniel Nyga (nyga@cs.tum.edu)
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

from branchandbound import BranchAndBound
from pracmln.mln.grounding.bnb import GroundingFactory

class RussianDoll(BranchAndBound):
    
    def __init__(self, mrf):
        BranchAndBound.__init__(self, mrf)
        self.lowerbounds = []
        for _ in self.varIdx2GndAtom:
            self.lowerbounds.append({})
            
    def search(self):
        
        # sort the formulas
        self.factories = [GroundingFactory(f, self.mrf) for f in sorted(self.formulas, key=lambda x: x.weight, reverse=True)]
        
        # sort the ground atoms
        atoms = []
        nonEvidenceVars = [i for i, _ in enumerate(self.vars) if not self._isEvidenceVariable(i)]
        atoms.extend([v for v in nonEvidenceVars if len(self.varIdx2GndAtom[v]) > 1])
        atoms.extend([v for v in nonEvidenceVars if len(self.varIdx2GndAtom[v]) == 1])
        atoms.extend([i for i, _ in enumerate(self.vars) if self._isEvidenceVariable(i)])
        self.mrf._clearEvidence()
        self._rd_recursive_expand(atoms)

    def _rd_recursive_expand(self, variables):
        if not len(variables) < 2:
            self._rd_recursive_expand(variables[1:])
        self.costs = 0.
        lb = self.upperbound
        print variables, lb
        self.upperbound = float('inf') # TODO: can this be improved?
        # call normal BnB search
        self._recursive_expand(variables, 0. if len(variables) == 1 else lb)
        
if __name__ == '__main__':
    from mln.MarkovLogicNetwork import MLN
    from logic import grammar
    from mln.database import Database
    mln = MLN()
    mln.declarePredicate('foo', ['x', 'y'], functional=[1])
    mln.declarePredicate('bar', ['y','z'])
     
    f = grammar.parseFormula('foo(?x1,?y1) ^ foo(?x2,?y1) ^ bar(?y3,Y) ^ bar(?y3, ?z2)')
    mln.addFormula(f, 1)
    f = grammar.parseFormula('!foo(?x1,?y1) v !foo(?x2,?y1) v !bar(?y3,Y) v !bar(?y3, ?z2)')
    mln.addFormula(f, 1.1)
#    mln.addDomainValue('x', 'Z')
     
    db = Database(mln)
    db.addGroundAtom('!foo(X, Fred)')
    db.addGroundAtom('!foo(X, Ann)')
    db.addGroundAtom('!bar(Fred, Z)')
    db.addGroundAtom('bar(Bob, Y)')
     
     
    mrf = mln.groundMRF(db, simplify=False)
     
    bnb = RussianDoll(mrf)
    bnb.search()
    print 'optimal solution (cost %f):' % bnb.upperbound
    for s in sorted(bnb.best_solution):
        print '', s, ':', bnb.best_solution[s]
         
    exit(0)
       
        
    