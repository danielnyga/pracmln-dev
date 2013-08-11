'''
Created on Aug 11, 2013

@author: nyga
'''
from mln.MarkovLogicNetwork import MLN
from logic import grammar
from mln.database import Database
from mln.util import strFormula, toClauseSet
from logic.fol import Negation
from logic.sat import DPLL
import math

if __name__ == '__main__':
    
    mln = MLN()
    mln.declarePredicate('foo', ['x'])
    mln.declarePredicate('bar', ['x','y'])
     
    f = grammar.parseFormula('foo(?x) ^ bar(?x, Y)')
    mln.addFormula(f, 1)
    f = grammar.parseFormula('foo(?x) ^ !bar(?x, Y)')
    mln.addFormula(f, 1)    
#     f = grammar.parseFormula('!foo(?x) ^ bar(?x, Z)')
#     mln.addFormula(f, 1)
#     f = grammar.parseFormula('!foo(?x) ^ !bar(?x, Z)')
#     mln.addFormula(f, 1)
    
     
    db = Database(mln)
    db.addGroundAtom('foo(X1)')
    db.addGroundAtom('bar(X1, Y)')
    
    db.addGroundAtom('foo(X2)')
    db.addGroundAtom('bar(X2, Y)')
    
    db.addGroundAtom('foo(X3)')
    
    mrf = mln.groundMRF(db, cwAssumption=True)
    
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # generate microtheories
    microtheories = {}
    for f in mln.formulas:
        gfs = mrf.groundingMethod.formula2GndFormulas[f]
        clauses = set()
        mt = []
        for gf in gfs:
            cnf = gf.toCNF()
            print cnf
            clauses =  toClauseSet(cnf)
            mt.extend(clauses)
        mtModels = []
        for gf in mrf.gndFormulas:
            negProp = Negation([gf]).toCNF()
            negProp = toClauseSet(negProp)
            if not DPLL(mt + negProp):
                mtModels.append(gf)
        microtheories[f] = mtModels
    for mt in microtheories:
        print mt, ':'
        print map(str, microtheories[mt])
    
    print 'Training data points:'
    for gf in mrf.gndFormulas:
        gf.weight = 1.0 / len(mrf.gndFormulas)
        gf.truth = 1.0 if gf.isTrue(mrf.evidence) else -1.0
        print strFormula(gf), 'is', gf.isTrue(mrf.evidence), '(%d)' % gf.truth
    
    def models(mt, gf):
        return 1.0 if gf in microtheories[mt] else -1.0
    
    def learnMT():
        bestMT = None
        bestErr = None
        for mt in microtheories:
            err = 0.
            for gf in mrf.gndFormulas:
#                 print mt, gf, gf.truth, '*', models(mt, gf)
                if models(mt, gf) * gf.truth < 0: 
                    err += gf.weight
            if bestMT is None or bestErr > err:
                bestMT = mt
                bestErr = err
        return bestMT, bestErr
    
    def printWeights():
        for gf in mrf.gndFormulas:
            print gf.weight, strFormula(gf), gf.truth
    
    mtWeights = {}
    for mt in microtheories: mtWeights[mt] = []
    
    # the AdaBoost procedure
    M = 10000
    for m in range(M):
#         print 'Iteration %d/%d' % (m+1, M)
        mt, err = learnMT()
        
        # evaluate the microtheory
        alpha = 0.5 * math.log((1. - err) / err)
        mtWeights[mt].append(alpha)
        
        # reweight the datapoints
        sumWeights = 0
        for gf in mrf.gndFormulas:
            gf.weight = gf.weight * math.exp(-gf.truth * models(mt, gf))
            sumWeights += gf.weight
        for gf in mrf.gndFormulas:
            gf.weight /= sumWeights
    print '---------'
    alphasum = sum(map(sum, mtWeights.values()))
    print '// formulas'
    for mt in microtheories:
        try: 
            w = 2. * sum(mtWeights[mt]) / alphasum - 1.
        except:
            w = -1.
        print '%.6f\t%s' % (w, strFormula(mt))
            
        
    
    
    
