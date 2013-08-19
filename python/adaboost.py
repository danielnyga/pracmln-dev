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
    mln.addFormulaTemplate(f, 1)
    f = grammar.parseFormula('foo(?x) ^ !bar(?x, Y)')
    mln.addFormulaTemplate(f, 1)    
    f = grammar.parseFormula('!foo(?x) ^ bar(?x, Y)')
    mln.addFormulaTemplate(f, 1)    
    f = grammar.parseFormula('!foo(?x) ^ !bar(?x, Y)')
    mln.addFormulaTemplate(f, 1)
#     f = grammar.parseFormula('!foo(?x) ^ !bar(?x, Y)')
#     mln.addFormulaTemplate(f, 1)
    
     
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
#         bestMT = None
#         bestErr = None
#         for mt in microtheories:
#             err = 0.
#             for gf in mrf.gndFormulas:
# #                 print mt, gf, gf.truth, '*', models(mt, gf)
#                 if models(mt, gf) * gf.truth < 0: 
#                     err += gf.weight
#             if bestMT is None or bestErr > err:
#                 bestMT = mt
#                 bestErr = err
#         return bestMT, bestErr
        alphas = []
        classifications = [0] * len(mrf.gndFormulas)
        for mt in microtheories:
            err = 0.
            for gf in mrf.gndFormulas:
#                 print mt, gf, gf.truth, '*', models(mt, gf)
                if models(mt, gf) * gf.truth < 0: 
#                     print err,
                    err += gf.weight
#                     print '+', gf.weight, '=', err
#             print 'err=', err
#             print (1. - err) / err
            alpha = 0.5 * math.log((1-err) / err)
            for i, gf in enumerate(mrf.gndFormulas):
                classifications[i] += (alpha * models(mt, gf))
            alphas.append(alpha)
        print alphas, classifications
        return alphas, classifications
    
    def printWeights():
        for gf in mrf.gndFormulas:
            print gf.weight, strFormula(gf), gf.truth
    
    # the AdaBoost procedure
    M = 10000
    alphas = [0] * len(microtheories)
    for m in range(M):
#         print 'Iteration %d/%d' % (m+1, M)
        printWeights()
        alpha, classifications = learnMT()
        
        # evaluate the microtheory
        for i, a in enumerate(alpha):
            alphas[i] += a
        
        # reweight the datapoints
        sumWeights = 0
        for gf, c in zip(mrf.gndFormulas, classifications):
            gf.weight = gf.weight * math.exp(-gf.truth * c)
            sumWeights += gf.weight
        for gf in mrf.gndFormulas:
            gf.weight /= sumWeights
    print '---------'
#     alphasum = sum(map(sum, mtWeights.values()))
    print '// formulas'
    for i, mt in enumerate(microtheories):
        print '%.6f\t%s' % (alphas[i], strFormula(mt))
            
        
    
    
    
