'''
Created on Aug 11, 2013

@author: nyga
'''
from mln.MarkovLogicNetwork import MLN, readMLNFromFile
from logic import grammar
from mln.database import Database, readDBFromFile
from mln.util import strFormula, toClauseSet
from logic.fol import Negation
from logic.sat import DPLL
import math

if __name__ == '__main__':
    
    mln = readMLNFromFile('foobar.mln')
    db = readDBFromFile(mln, 'foobar.db')
    
    mrf = mln.groundMRF(db, cwAssumption=True)
    
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # generate microtheories
    def generate_microtheories(mrf):
        microtheories = {}
        for f in mln.formulas:
            gfs = mrf.groundingMethod.formula2GndFormulas[f]
#             gndAtomIndices = set()
#             for gf in gfs:
#                 gndAtomIndices.update(gf.idxGroundAtoms())
            mtModels = gfs
#             for gf in mrf.gndFormulas:
#                 if (set(gf.idxGroundAtoms()) & gndAtomIndices):
#                     mtModels.append(gf)
            microtheories[f] = mtModels
        return microtheories
    
    
    print 'Training data points:'
    for gf in mrf.gndFormulas:
        gf.weight = 1.0 / len(mrf.gndFormulas)
        gf.truth = 1.0 if gf.isTrue(mrf.evidence) else -1.0
        print strFormula(gf), 'is', gf.isTrue(mrf.evidence), '(%d)' % gf.truth
    print '---'
    
    def models(mt, gf, prob=None):
        if prob is not None:
            return prob if gf in microtheories[mt] else (1-prob)
        return 1.0 if gf in microtheories[mt] else 0.
    
    def weighted_entropy(gfs):
        trueGFs = [gf for gf in gfs if gf.truth == 1]
        falseGFs = [gf for gf in gfs if gf.truth == -1]
        totalWeights = sum(map(lambda x: x.weight, gfs))
        probTrue = sum(map(lambda x: x.weight, trueGFs)) / totalWeights
        probFalse = sum(map(lambda x: x.weight, falseGFs)) / totalWeights
        return -(probTrue * math.log(probTrue, 2) + probFalse * math.log(probFalse, 2))
    
    class Dummy(object): pass
    
    def learnMT():
        bestMT = None
        bestErr = None
        for mt in microtheories:
            err = 0.
            sumWeights = sum(map(lambda x: x.weight, microtheories[mt]))
            localWeights = {}
            for gf in microtheories[mt]:
                try:
                    localWeights[gf] = gf.weight / sumWeights
                except: localWeights[gf] = 0.
            for gf in microtheories[mt]:
                print mt, '|==' if models(mt, gf) == 1 else '|=/=', gf, 'but' if models(mt, gf) * gf.truth < 0 else 'and', gf, 'is', gf.truth 
                if models(mt, gf) * gf.truth < 0: 
                    err += localWeights[gf]
#             print 'ent after:', entAfter
            performance = abs(err - .5) * sumWeights
            print 'performance:', performance 
            if bestMT is None or bestErr < performance:
                bestMT = mt
                bestErr = performance
                globErr = err
            print mt, 'has error', err
        return bestMT, globErr
    
    def printWeights():
        for gf in mrf.gndFormulas:
            print gf.weight, strFormula(gf), gf.truth
            
    def infer():
        # caution: this is extremely expensive
        print 'generating possible worlds...'
        worlds = mrf._getWorlds()
        print ' created %d worlds.' % len(worlds)
    
    def iter_worlds(mrf):
        evidence = mrf.getEvidenceDatabase()
        freeGndAtoms = set(mrf.gndAtoms.keys()).difference(evidence.keys())
        for world in __iter_worlds(mrf, freeGndAtoms, evidence):
            yield world
        
    def __iter_worlds(mrf, freeAtoms, assignment):
        if len(freeAtoms) == 0:
            yield assignment
            return 
        for atom in freeAtoms: break
        for val in (True, False):
            for world in __iter_worlds(mrf, freeAtoms-set([atom]), dict(assignment.viewitems() | {atom: val}.items())):
                yield world
    
    def compute_world_prob(mrf, mts, world):
        prob = .0
        Z = 0.
        for w in iter_worlds(mrf):
            val = eval_world(mrf, mts, w)
            Z += val
            if world == w: prob = val
        return prob / Z
    
    def eval_world(mrf, mts, world_values):
        score = .0
        evidenceBackup = mrf.getEvidenceDatabase()
        mrf.setEvidence(world_values)
        for gf in mrf.gndFormulas:
            counts = 0
            for mt in mts:
                if models(mt, gf) == 0.: continue
                counts += len(mts[mt])
                sumMT = sum(map(lambda x: 2 * x - 1, mts[mt]))
                score += sumMT * (1. if mrf._isTrueGndFormulaGivenEvidence(gf) else -1)
            score /= counts
        score /= len(mrf.gndFormulas)
        score = 0.5 * (score + 1)
        mrf.setEvidence(evidenceBackup)
        return score

    def infer(mrf, mts, query_pred): 
        query_atoms = mrf._getPredGroundings(query_pred)
        probs = {}
        for w in iter_worlds(mrf):
            for q in query_atoms:
                if not len(w.viewitems() & {q: True}.items()) == 0:
                    probs[q] = probs.get(q, .0) + compute_world_prob(mrf, mts, w)
        return probs

    microtheories = generate_microtheories(mrf)
        
    for mt in microtheories:
        print mt, ':'
        print map(str, microtheories[mt])
    
    # the AdaBoost procedure
    M = 100
    mt2alphas = {}
    for m in range(M):
        print 'Iteration %d/%d' % (m+1, M)
        printWeights()
        mt, err = learnMT()
        
        alpha = 1-err
        print '  err = %.2f, prob=%.2f, alpha = %.2f with f=%s' % (err, (1-err), alpha, strFormula(mt))
        
        # evaluate the microtheory
        a_mt = mt2alphas.get(mt, [])
        mt2alphas[mt] = a_mt
        a_mt.append(alpha)
        
        # reweight the datapoints
        for gf in microtheories[mt]:
            gf.weight = gf.weight * math.exp(-gf.truth * (2 * alpha - 1))
        sumWeights = sum(map(lambda x: x.weight, mrf.gndFormulas))
        for gf in mrf.gndFormulas:
            gf.weight /= sumWeights
    print
    alphasum = sum(map(sum, mt2alphas.values()))
    
    learnedMLN = mln.duplicate()
    learnedMLN.formulaTemplates = []
    learnedMLN.formulas = None
    print mt2alphas
    print '--- formulas ---'
    for i, mt in enumerate(microtheories):
        w = sum(map(lambda x: 2 * x - 1, mt2alphas[mt]))
        print '%.6f %s' % (w, strFormula(mt))
        learnedMLN.addFormulaTemplate(mt, w)
    
#     exit(0)
    print
    print '--- inference ---'
    # ground with test db
    testDB = readDBFromFile(mln, 'foobartest.db')
    mrf = mln.groundMRF(testDB)
    microtheories = generate_microtheories(mrf)
    print
    print '--- microtheories ---'
    for mt, gnd in microtheories.iteritems():
        print mt, '|=',  map(strFormula, gnd)
        
    print
    print '--- query probabilities ---'
    for q in ('foo', 'bar'):
        for prob in infer(mrf, mt2alphas, q).iteritems():
            print '%.6f\t%s' % (prob[1], prob[0])

    print
    print '--- world probabilities ---'
    s = .0
    for w in iter_worlds(mrf):
        prob = compute_world_prob(mrf, mt2alphas, w)
#         prob = eval_world(mrf, mt2alphas, w)
        backup = mrf.getEvidenceDatabase()
        mrf.setEvidence(w)
        print '%.4f\t%s' % (prob, w)
        for gf in mrf.gndFormulas:
            print ' ', gf, 'is', mrf._isTrueGndFormulaGivenEvidence(gf)
        s += prob
        mrf.setEvidence(backup)
    print 'probabilities sum to %f' % s
        
        
    
    
    
