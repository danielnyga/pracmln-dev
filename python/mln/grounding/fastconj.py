# MARKOV LOGIC NETWORKS
#
# (C) 2011-2014 by Daniel Nyga (nyga@cs.tum.edu)
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

from mln.grounding.default import DefaultGroundingFactory
import logging
from logic.common import Logic
import types
from multiprocessing.pool import Pool
from utils.multicore import with_tracing
import itertools

    
# this readonly global is for multiprocessing to exploit copy-on-write
# on linux systems
global_fastConjGrounding = None

# multiprocessing function
def create_formula_groundings(formula):
    gndFormulas = []
#     for formula in formulas:
    if global_fastConjGrounding.mrf.mln.logic.isConjunctionOfLiterals(formula):
        for gndFormula in global_fastConjGrounding.iterConjunctionGroundings(formula):
            gndFormula.isHard = formula.isHard
            gndFormula.weight = formula.weight
#                 groundingFactory.mrf._addGroundFormula(gndFormula, idxFormula, None)
            gndFormula.fIdx = formula.idx
            gndFormulas.append(gndFormula)
    else:
        for gndFormula, _ in formula.iterGroundings(global_fastConjGrounding.mrf, simplify=True):
            gndFormula.isHard = formula.isHard
            gndFormula.weight = formula.weight
            gndFormula.fIdx = formula.idx
            gndFormulas.append(gndFormula)
    #                 groundingFactory.mrf._addGroundFormula(gndFormula, idxFormula, referencedGndAtoms)
    return gndFormulas
    

class FastConjunctionGrounding(DefaultGroundingFactory):
    
    def _getEvidenceBlockData(self):
        # build up data structures
        self.evidenceBlocks = [] # list of pll block indices where we know the true one (and thus the setting for all of the block's atoms)
        self.blockExclusions = {} # dict: pll block index -> list (of indices into the block) of atoms that mustn't be set to true
        for idxBlock, (idxGA, block) in enumerate(self.mrf.pllBlocks): # fill the list of blocks that we have evidence for
            if block != None:
                haveTrueone = False
                falseones = []
                for i, idxGA in enumerate(block):
                    ev = self.mrf._getEvidence(idxGA, False)
                    if ev == 1:
                        haveTrueone = True
                        break
                    elif ev == 0:
                        falseones.append(i)
                if haveTrueone:
                    self.evidenceBlocks.append(idxBlock)
                elif len(falseones) > 0:
                    self.blockExclusions[idxBlock] = falseones
            else:
                if self.mrf._getEvidence(idxGA, False) != None:
                    self.evidenceBlocks.append(idxBlock)

    
    def prepareGrounding(self): pass
#         self.mrf._getPllBlocks()
#         self.mrf._getEvidenceBlockData()
        

    def iterConjunctionGroundings(self, formula):
        '''
        Recursively generate the groundings of a conjunction that do _not_
        have a definite truth value yet given the evidence.
        '''
        log = logging.getLogger(self.__class__.__name__)
        logic = self.mrf.mln.logic
        # make a copy of the formula to avoid side effects
        formula = formula.ground(self.mrf, {}, allowPartialGroundings=True)
        conjunction_ = logic.conjunction([formula, logic.truefalse(1)]) if not hasattr(formula, 'children') else formula
        # make equality constraints access their variable domains
        # this is a _really_ dirty hack but it does the job ;-)
        variables = conjunction_.getVariables(self.mrf.mln)
        def getEqualityVariables(self, mln):
            var2dom = {}
            for c in self.params:
                if mln.logic.isVar(c):
                    var2dom[c] = variables[c]
            return var2dom 
        # rearrange children
        children = list(conjunction_.children)
        conjunction = []
        for child in list(children):
            if isinstance(child, Logic.Equality):
                conjunction.append(child)
                children.remove(child)
                # replace the getVariables method in this equality instance
                # by our customized one
                setattr(child, 'getVariables', types.MethodType(getEqualityVariables, child))
        for child in list(children):
            if child.predName in self.mrf.mln.blocks: 
                conjunction.append(child)
                children.remove(child)
        conjunction.extend(children)
        conjunction = logic.conjunction(conjunction)
        for gndFormula in self._iterConjunctionGroundings(conjunction, 0, len(conjunction.children), self.mrf, {}):
            yield gndFormula
            
            
    def _iterConjunctionGroundings(self, formula, litIdx, numChildren, mrf, assignment):
        log = logging.getLogger(self.__class__.__name__)
        if litIdx == numChildren:
#             if formula.isTrue(mrf.evidence) is not None: # the gnd formula is rendered true by the evidence. skip this one
#                 return
            gndFormula = formula.ground(mrf, assignment, simplify=True)#.simplify(mrf)
            if isinstance(gndFormula, Logic.TrueFalse): return
            else: yield gndFormula
            return
        lit = formula.children[litIdx]
        for varAssignment in lit.iterTrueVariableAssignments(mrf, mrf.evidence, truthThreshold=.0, strict=True, includeUnknown=True, partialAssignment=assignment):
            if varAssignment == {}:
                if len(set(lit.getVariables(mrf.mln).keys()).difference(assignment.keys())) > 0 or \
                    lit.ground(mrf, assignment).isTrue(mrf.evidence) == 0: 
                    return
            assignment = dict(assignment)
            assignment.update(varAssignment)
            for gndFormula in self._iterConjunctionGroundings(formula, litIdx+1, numChildren, mrf, assignment):
                yield gndFormula
            
        
    def _createGroundFormulas(self):
        global global_fastConjGrounding
        mrf = self.mrf
        assert len(mrf.gndAtoms) > 0
        log = logging.getLogger(self.__class__.__name__)
        # generate all groundings
        log.info('Grounding formulas...')
        log.debug('Ground formulas (all should have a truth value):')
        multiCPU = self.params.get('useMultiCPU', False)
        if multiCPU:
            for i, f in enumerate(mrf.formulas):
                f.idx = i
            global_fastConjGrounding = self
            pool = Pool()
            log.info('Multiprocessing enabled using %d cores.' % pool._processes)
            try:
                gndFormulas = pool.map(with_tracing(create_formula_groundings), mrf.formulas)
                for gndFormula in itertools.chain(itertools.chain(*gndFormulas)):
                    mrf._addGroundFormula(gndFormula, gndFormula.fIdx, None)
            except:
                pool.terminate()
                pool.join()
        else:
            for idxFormula, formula in enumerate(mrf.formulas):
                if mrf.mln.logic.isConjunctionOfLiterals(formula):
                    for gndFormula in self.iterConjunctionGroundings(formula):
                        gndFormula.isHard = formula.isHard
                        gndFormula.weight = formula.weight
                        mrf._addGroundFormula(gndFormula, idxFormula, None)
                else:
                    for gndFormula, referencedGndAtoms in formula.iterGroundings(mrf, simplify=True):
                        gndFormula.isHard = formula.isHard
                        gndFormula.weight = formula.weight
                        mrf._addGroundFormula(gndFormula, idxFormula, referencedGndAtoms)
        log.info('created %d ground formulas.' % len(mrf.gndFormulas))
            