import unittest
from mln import MLN
import os
import sys
from mln.methods import *
from pprint import pprint
from mln.MarkovLogicNetwork import readMLNFromFile
from wcsp.converter import WCSPConverter
from wcsp.wcsp import WCSP

class MLNTestCase(unittest.TestCase):
    
    def setUp(self):
        join = os.path.join
        self.modelsDir = join("..", "models")
        self.simpleLearnDir = join(self.modelsDir, "simpleLearning")
        self.simpleLearnDB = join(self.simpleLearnDir, "train.db")
        self.smokingDir = join(self.modelsDir, "smokers")
        self.smokingDB = join(self.smokingDir, "smoking-train.db")
        self.studentDir = join(self.modelsDir, "student_course")
        self.studentDB = join(self.studentDir, "1each.db")
        self.probConstrDir = join(self.modelsDir, "probConstraints")
        self.posteriorCDir = join(self.probConstrDir, "posterior")
        self.priorCDir = join(self.probConstrDir, "prior")
        self.wcspDir = join(self.modelsDir, 'wcsp_conversion')
    
    def assertApproxEqual(self, a, b, delta = 1e-5):
        self.assertTrue(abs(a-b) <= delta, "%f !~ %f [max. dev. %f]" % (a, b, delta))
    
    def assertApproxListEqual(self, a, b, delta = 1e-5):
        self.assertEqual(len(a), len(b))
        for i in xrange(len(a)):
            self.assertApproxEqual(a[i], b[i], delta)
    
    def getSmokersModel(self):
        return readMLNFromFile(os.path.join(self.smokingDir, "smoking.mln"))
    
    def getSimpleLearningModel(self):
        return readMLNFromFile(os.path.join(self.simpleLearnDir, "simple.mln"))
    
    def test_learnLL(self):
        mln = self.getSimpleLearningModel()
        newMLN = mln.learnWeights([self.simpleLearnDB], ParameterLearningMeasures.LL, optimizer="bfgs")
        weights = newMLN.getWeights()
        correctWeights = [12.134464056525509, -4.0448208849872236, -8.0896429592875982, 4.0448220742997858]
        self.assertApproxListEqual(weights, correctWeights)

    def test_learnPLL(self):
        mln = self.getSimpleLearningModel()
        newMLN = mln.learnWeights([self.simpleLearnDB], ParameterLearningMeasures.PLL, optimizer="bfgs")
        weights = newMLN.getWeights()
        correctWeights = [16.946119791748266, -5.6487239615488454, -11.297429358877265, 5.6487053973271903]
        self.assertApproxListEqual(weights, correctWeights)
    
    def test_learnBPLL(self):
        mln = self.getSimpleLearningModel()
        newMLN = mln.learnWeights([self.simpleLearnDB], ParameterLearningMeasures.BPLL, optimizer="bfgs")
        weights = newMLN.getWeights()
        correctWeights = [16.946119791748266, -5.6487239615488454, -11.297429358877265, 5.6487053973271903]
        self.assertApproxListEqual(weights, correctWeights)

    def test_learnBPLL_Smoking(self):        
        mln = self.getSmokersModel()
        newMLN = mln.learnWeights([self.smokingDB], ParameterLearningMeasures.BPLL, optimizer="bfgs")
        weights = newMLN.getWeights()
        correctWeights = [0.64669600105802549, 1.519900134095767]
        self.assertApproxListEqual(weights, correctWeights)

    def test_learnBPLLCG_Smoking(self):        
        mln = self.getSmokersModel()
        newMLN = mln.learnWeights([self.smokingDB], ParameterLearningMeasures.BPLL_CG, optimizer="bfgs")
        weights = newMLN.getWeights()
        correctWeights = [0.64669600105802549, 1.519900134095767]
        self.assertApproxListEqual(weights, correctWeights)
    
    def __test_learnPLL_Smoking(self):        
        mln = self.getSmokersModel()
        newMLN = mln.learnWeights([self.smokingDB], ParameterLearningMeasures.PLL, optimizer="bfgs")
        correctWeights = [0.664496216335284, 1.8004196461831026]
        weights = newMLN.getWeights()
        self.assertApproxListEqual(weights, correctWeights)
    
    def test_groundAMLN(self):
        mln = readMLNFromFile(os.path.join(self.studentDir, "student_course2.a.mln"))
        mrf = mln.groundMRF(self.studentDB)
        weights = map(lambda p: float(p[0]), mrf.getGroundFormulas())
        correctWeights = [1.5604290525533999, 3.6511741317144004, -0.7968133588156, 7.0145072690164003, 0.151252120947, -1.6360797755282002, -1.5131502151878, -8.4313192249819995, -0.38454063647300002, -1.16283955905, 1.3519705598595, -2.8760315103522003]
        self.assertApproxListEqual(weights, correctWeights)
    
    def test_groundWithVars(self):
        mln = readMLNFromFile(os.path.join(self.studentDir, "student_course2_simLearned.mln"))
        mln.write(sys.stdout)
        mrf = mln.groundMRF(self.studentDB)
        weights = map(lambda p: float(p[0]), mrf.getGroundFormulas())
        correctWeights = [-0.40546510810816444, -1.0986122886681098, -0.22314355131420957, -1.6094379124341012, -7.3508372506616082, -0.0006422607799453446, -1.0986122886681098, -0.40546510810816427, -6.1468644463356723, -0.0021424753776469402, 27.350837250661606, 27.350837250661606]
        self.assertApproxListEqual(weights, correctWeights)
    
    def test_softEvidenceIPFPM(self):
        mln = readMLNFromFile(os.path.join(self.posteriorCDir, "simple.mln"))
        mrf = mln.groundMRF(os.path.join(self.posteriorCDir, "test.db"))
        results = map(float, (mrf.inferIPFPM("attr")))
        correctResults = [0.6666666666666666, 0.10]
        self.assertApproxListEqual(results, correctResults)

    def test_softEvidenceMCSATPC(self):
        mln = readMLNFromFile(os.path.join(self.posteriorCDir, "simple.mln"))
        mrf = mln.groundMRF(os.path.join(self.posteriorCDir, "test.db"))
        results = map(float, (mrf.inferMCSAT("attr")))
        correctResults = [0.6666666666666666, 0.10]
        self.assertApproxListEqual(results, correctResults, 0.04)
        
    def test_wcspConversion(self):
        mln = readMLNFromFile(os.path.join(self.wcspDir, 'conv.mln'))
#         mln.write(sys.stdout)
        mrf = mln.groundMRF(os.path.join(self.wcspDir, 'evidence.db'))
        resultWCSP = WCSP()
        resultWCSP.read(open(os.path.join(self.wcspDir, 'result.wcsp')))
#         resultWCSP.write(sys.stdout)
        converter = WCSPConverter(mrf)
        wcsp = converter.convert()
#         wcsp.write(sys.stdout)
        self.assertTrue(wcsp == resultWCSP, 'WCSP conversion test failed.')
    
    # TODO:
    #  - multiple database learning
    #  - learning with fixed weights
    #  - prior prob. constraints
    #  - learning with constant expansion
    #  - inference
        
if __name__ == '__main__':
    runAll = True
    test = "test_wcspConversion"
#     test = 'test_learnBPLL'
    if runAll:
        unittest.main()
    else:
        testCase = MLNTestCase(test)
        testCase.run()