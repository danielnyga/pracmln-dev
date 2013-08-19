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
    
    mln = readMLNFromFile('object-detection.mln')     
    db = readDBFromFile(mln, 'train.db')
    
    mrf = mln.groundMRF(db, cwAssumption=True)
    
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # generate microtheories
    def generate_microtheories(mrf):
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
            for mt in mts:
                count = 0
                if all(map(lambda f: mrf._isTrueGndFormulaGivenEvidence(f) != False, microtheories[mt])):
                    score += 2 * (models(mt, gf, sum(mts[mt]))-1)# * (1. if mrf._isTrueGndFormulaGivenEvidence(gf) else -1.)
                    count += 1
            if count == 0: continue
            score /= count
        score /= len(mrf.gndFormulas)
        score = 0.5 * score + 1
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
#         printWeights()
        mt, err = learnMT()
        
        if abs(err - .5) < 1e-10 or err < 1e-10 or (1-err) < 1e-10:
            print 'learning has finished early.'
            break
#         alpha = .5 * math.log((1.-err) / err)
        alpha = 2. * (1. - err) - 1.
        print '  err = %.2f, prob=%.2f, alpha = %.2f with f=%s' % (err, (1-err), alpha, strFormula(mt))
        
        # evaluate the microtheory
        a_mt = mt2alphas.get(mt, [])
        mt2alphas[mt] = a_mt
        a_mt.append(alpha)
        
        # reweight the datapoints
        sumWeights = 0
        for gf in mrf.gndFormulas:
            gf.weight = gf.weight * math.exp(-gf.truth * 2 * (models(mt, gf, (1-err)))-1)
            sumWeights += gf.weight
        for gf in mrf.gndFormulas:
            gf.weight /= sumWeights
    print
    alphasum = sum(map(sum, mt2alphas.values()))
    
    learnedMLN = mln.duplicate()
    learnedMLN.formulaTemplates = []
    learnedMLN.formulas = None
    print '--- formulas ---'
    for i, mt in enumerate(microtheories):
        w = sum(mt2alphas.get(mt, [0]))
        print '%.6f %s' % (w, strFormula(mt))
        learnedMLN.addFormulaTemplate(mt, w)
    
    print
    print '--- inference ---'
    # ground with test db
    testDB = readDBFromFile(mln, 'test.db')
    mrf = mln.groundMRF(testDB)
    microtheories = generate_microtheories(mrf)
    print
    print '--- microtheories ---'
    for mt, gnd in microtheories.iteritems():
        print mt, '|=',  map(strFormula, gnd)
        
    print
    print '--- query probabilities ---'
    for prob in infer(mrf, mt2alphas, 'obj').iteritems():
        print '%.6f\t%s' % (prob[1], prob[0])
    for prob in infer(mrf, mt2alphas, 'obs').iteritems():
        print '%.6f\t%s' % (prob[1], prob[0])
    print
    print '--- world probabilities ---'
    s = .0
    for w in iter_worlds(mrf):
        prob = compute_world_prob(mrf, mt2alphas, w)
        backup = mrf.getEvidenceDatabase()
        mrf.setEvidence(w)
        print '%.4f\t%s' % (prob, w)
        for gf in mrf.gndFormulas:
            print ' ', gf, 'is', mrf._isTrueGndFormulaGivenEvidence(gf)
        s += prob
        mrf.setEvidence(backup)
    print 'probabilities sum to %f' % s
        
        
    
    
    
