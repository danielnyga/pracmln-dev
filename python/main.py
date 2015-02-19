'''
Created on Feb 16, 2015

@author: nyga
'''
from mln.mln import readMLNFromFile
from mln.database import readDBFromFile
from experimental.mlnboost import MLNBoost
from mln.grounding.default import EqualityConstraintGrounder

if __name__ == '__main__':
    
    mln = readMLNFromFile('/home/nyga/code/pracmln/models/object-detection-new.mln')
    dbs = readDBFromFile(mln, '/home/nyga/code/pracmln/models/scenes-new.db')
    mln_ = mln.materializeFormulaTemplates(dbs)
    
#     eqg = EqualityConstraintGrounder(mln_, EqualityConstraintGrounder.getVarDomainsFromFormula(mln, 'object(?c1, ?o1) ^ object(?c2, ?o2)', '?o1', '?o2'), 
#                                      #mln_.logic.equality(['?o1', '?o2']), 
#                                      mln_.logic.equality(['?o1', '?o2'], negated=False))
    mln_.formulas = mln.formulas
    mlnboost = MLNBoost(mln_, dbs)
    mlnboost.run()
    
