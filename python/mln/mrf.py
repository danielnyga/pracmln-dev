# -*- coding: utf-8 -*-
#
# Ground Markov Random Fields
#
# (C) 2012-2013 by Daniel Nyga (nyga@cs.uni-bremen.de)
# (C) 2006-2011 by Dominik Jain (jain@cs.tum.edu)
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

from utils import dict_union
import logging
from database import readDBFromFile, Database
from util import mergeDomains
import copy
import sys
import re
from util import strFormula
from logic import FirstOrderLogic
from math import *
from util import toCNF, logx
from methods import *
import time
from inference import *
import random
from grounding import *

POSSWORLDS_BLOCKING = True


class AtomicBlock(object):
    '''
    Represents a (mutually exclusive) block of ground atoms.
    '''
    
    def __init__(self, blockname, *gndatoms):
        self.gndatoms = list(gndatoms)
        self.name = blockname
    
    
    def iteratoms(self):
        '''
        Yields all ground atoms in this block, sorted by atom index ascending
        '''
        for atom in sorted(self.gndatoms, key=lambda a: a.idx):
            yield atom
    
    
    def getNumberOfPossibleWorlds(self):
        raise Exception('%s does not implement getNumberOfPossibleWorlds()' % self.__class__.__name__)
    
    
    def generatePossibleWorldTuples(self, evidence=None):
        '''
        evidence mapping gnd atom indices to truth values
        '''
        raise Exception('%s does not implement generatePossibleWorldTuples()' % self.__class__.__name__)
    
    
    def __str__(self):
        return '%s: %s' % (self.name, ','.join(map(str, self.gndatoms)))


class BinaryBlock(AtomicBlock):
    '''
    Represents a binary ("normal") ground atom with the two states 1 and 0
    '''

    def getNumberOfPossibleWorlds(self):
        return 2


    def generatePossibleWorldTuples(self, evidence=None):
        '''
        Yields possible world values of this atom block.
        '''
        if evidence is None:
            evidence = {}
        gndatom = self.gndatoms[0]
        if gndatom.idx in evidence:
            yield evidence[gndatom.idx]
            return
        for t in (0, 1):
            yield (t,)


class MutexBlock(AtomicBlock):
    '''
    Represents a mutually exclusive block of ground atoms.
    '''
    
    def getNumberOfPossibleWorlds(self):
        return len(self.gndatoms)
    
    
    def generatePossibleWorldTuples(self, evidence=None):
        if evidence is None:
            evidence = {}
        for world in self._generatePossibleWorldTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generatePossibleWorldTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple([tuple(map(lambda x: 1 if x == 1 else 0, valpattern))])
            return
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)


class SoftMutexBlock(AtomicBlock):
    '''
    Represents a soft mutex block of ground atoms.
    '''
    
    def getNumberOfPossibleWorlds(self):
        return len(self.gndatoms) + 1


    def generatePossibleWorldTuples(self, evidence=None):
        if evidence is None:
            evidence = {}
        for world in self._generatePossibleWorldTuplesRecursive(self.gndatoms, [], evidence):
            yield world
    
    
    def _generatePossibleWorldTuplesRecursive(self, gndatoms, assignment, evidence):
        atomindices = map(lambda a: a.idx, gndatoms)
        valpattern = []
        for mutexatom in atomindices:
            valpattern.append(evidence.get(mutexatom, None))
        # at this point, we have generated a value pattern with
        # all values that are fixed by the evidence argument and None
        # for all others
        trues = sum(filter(lambda x: x == 1, valpattern))
        if trues > 1: # sanity check
            raise Exception("More than one ground atom in mutex variable is true: %s" % str(self))
        if trues == 1: # if the true value of the mutex var is in the evidence, we have only one possibility
            yield tuple([tuple(map(lambda x: 1 if x == 1 else 0, valpattern))])
            return
        for i, val in enumerate(valpattern): # generate a value tuple with a true value for each atom which is not set to false by evidence
            if val == 0: continue
            elif val is None:
                values = [0] * len(valpattern)
                values[i] = 1
                yield tuple(values)
        yield tuple([0] * len(atomindices))
                            


class MRF(object):
    '''
    Represents a ground Markov Random Field

    members:
        gndAtoms:
            maps a string representation of a ground atom to a fol.GroundAtom object
        gndAtomsByIdx:
            dict: ground atom index -> fol.GroundAtom object
        evidence:
            list: ground atom index -> truth values
        gndBlocks:
            dict: block name -> list of ground atom indices
        gndBlockLookup:
            dict: ground atom index -> block name
        gndAtomOccurrencesInGFs
            dict: ground atom index -> ground formula
        gndFormulas:
            list of grounded formula objects
        pllBlocks:
            list of *all* the ground blocks, including trivial blocks consisting of a single ground atom
            each element is a tuple (ground atom index, list of ground atom indices) where one element is always None
    '''


    def __init__(self, mln, db, groundingMethod='DefaultGroundingFactory', cwAssumption=False, verbose=False, simplify=False, initWeights=False, **params):
        '''
        - db:        database filename (.db) or a Database object
        - params:    dict of keyword parameters. Valid values are:
            - simplify: (True/False) determines if the formulas should be simplified
                        during the grounding process.
            - verbose:  (True/False) Verbose mode on/off
            - groundingMethod: (string) name of the grounding factory to be used (default: DefaultGroundingFactory)
            - initWeights: (True/False) Switch on/off heuristics for initial weight determination (only for learning!)
        '''
        log = logging.getLogger(self.__class__.__name__)
        self.mln = mln
        self.evidence = None
        self.evidenceBackup = {}
#         self.softEvidence = list(mln.posteriorProbReqs) # constraints on posterior 
                                                        # probabilities are nothing but 
                                                        # soft evidence and can be handled in exactly the same way
        log.debug('Formula simplification switched %s.' % {True: 'on', False: 'off'}[simplify])
        # ground members
        self.gndAtoms = {}
        self.gndBlockLookup = {}
        self.gndBlocks = {}
        self.gndAtomsByIdx = {}
        self.gndFormulas = []
        self.gndAtomOccurrencesInGFs = []
        self.gndAtomicBlocks = {}
        self.gndAtom2AtomicBlock = {}
        
        if type(db) == str:
            db = readDBFromFile(self.mln, db)
        elif isinstance(db, Database):
            pass
        else:
            raise Exception("Not a valid database argument (type %s)" % (str(type(db))))
        self.db = db
        # materialize MLN formulas
#         if self.mln.formulas is None:
#             db = self.mln.materializeFormulaTemplates([db],verbose)[0]
        self.formulas = list(self.mln.formulas) # copy the list of formulas, because we may change or extend it
        # get combined domain
        self.domains = mergeDomains(self.mln.domains, db.domains)
        log.debug('MRF domains:')
        for d in self.domains.items():
            log.debug(d)
            
        # materialize formula weights
        self._materializeFormulaWeights(verbose)

        self.closedWorldPreds = list(self.mln.closedWorldPreds)
        self.probreqs = list(self.mln.probreqs)
        self.posteriorProbReqs = list(self.mln.posteriorProbReqs)
        self.predicates = copy.deepcopy(self.mln.predicates)
        self.templateIdx2GroupIdx = self.mln.templateIdx2GroupIdx
        #log.debug('grounding the following MLN:')
        #self.mln.write(sys.stdout, color=True)
        #log.debug('grounding with the following database:')
        #db.write(sys.stdout, color=True)
        # grounding
        log.info('Loading %s...' % groundingMethod)
        groundingMethod = eval('%s(self, db, **params)' % groundingMethod)
        self.groundingMethod = groundingMethod
        groundingMethod.groundMRF(cwAssumption=cwAssumption, simplify=simplify)
        #og.debug('ground atoms  vs. evidence' + (' (all should be known):' if cwAssumption else ':'))
#         for a in self.gndAtoms.values():
#             log.debug('%s%s -> %2.2f' % (('%d' % a.idx).ljust(5), a, self.evidence[a.idx]))
        assert len(self.gndAtoms) == len(self.evidence)
        for gndblock in self.gndAtomicBlocks.values():
            print gndblock
            for world in gndblock.generatePossibleWorldTuples():
                print world

    def getHardFormulas(self):
        '''
        Returns a list of all hard formulas in this MRF.
        '''
        return [f for f in self.formulas if f.weight is None]

    def _getPredGroundings(self, predName):
        '''
        Gets the names of all ground atoms of the given predicate.
        '''
        # get the string represenation of the first grounding of the predicate
        if predName not in self.predicates:
            raise Exception('Unknown predicate "%s" (%s)' % (predName, map(str, self.predicates)))
        domNames = self.predicates[predName]
        params = []
        for domName in domNames:
            params.append(self.domains[domName][0])
        gndAtom = "%s(%s)" % (predName, ",".join(params))
        # get all subsequent groundings (by index) until the predicate name changes
        groundings = []
        idx = self.gndAtoms[gndAtom].idx
        while True:
            groundings.append(gndAtom)
            idx += 1
            if idx >= len(self.gndAtoms):
                break
            gndAtom = str(self.gndAtomsByIdx[idx])
            if self.mln.logic.parseAtom(gndAtom)[0] != predName:
                break
        return groundings

    def _getPredGroundingsAsIndices(self, predName):
        '''
        Get a list of all the indices of all groundings of the given predicate
        '''
        # get the index of the first grounding of the predicate and the number of groundings
        domNames = self.predicates[predName]
        params = []
        numGroundings = 1
        for domName in domNames:
            params.append(self.domains[domName][0])
            numGroundings *= len(self.domains[domName])
        gndAtom = "%s(%s)" % (predName, ",".join(params))
        if gndAtom not in self.gndAtoms: return []
        idxFirst = self.gndAtoms[gndAtom].idx
        return range(idxFirst, idxFirst + numGroundings)

    def _materializeFormulaWeights(self, verbose=False):
        '''
        materialize all formula weights.
        '''
        max_weight = 0
        for f in self.formulas:
            if f.weight is not None:
                w = str(f.weight)
                while "$" in w:
                    try:
                        w, numReplacements = re.subn(r'\$\w+', self.mln._substVar, w)
                    except:
                        sys.stderr.write("Error substituting variable references in '%s'\n" % w)
                        raise
                    if numReplacements == 0:
                        raise Exception("Undefined variable(s) referenced in '%s'" % w)
                w = re.sub(r'domSize\((.*?)\)', r'self.domSize("\1")', w)
                try:
                    f.weight = float(eval(w))
                except:
                    sys.stderr.write("Evaluation error while trying to compute '%s'\n" % w)
                    raise
                max_weight = max(abs(f.weight), max_weight)

        # set weights of hard formulas
        hard_weight = 20 + max_weight
        self.hard_weight = hard_weight
        hard_formulas = self.getHardFormulas()
        if verbose: print "setting %d hard weights to %f" % (len(hard_formulas), hard_weight)
        for f in hard_formulas:
            if verbose: print "  ", strFormula(f)
            f.weight = hard_weight

    def addGroundAtom(self, gndatom):
        '''
        Adds a ground atom to the set (actually it's a dict) of ground atoms.
        gndLit: a fol.GroundAtom object
        '''
        if str(gndatom) in self.gndAtoms:
            return
        atomIdx = len(self.gndAtoms)
        gndatom.idx = atomIdx
        self.gndAtomsByIdx[gndatom.idx] = gndatom
        self.gndAtoms[str(gndatom)] = gndatom
        self.gndAtomOccurrencesInGFs.append([])
        
        # check if atom is in block and update the lookup
        mutex = self.mln.blocks.get(gndatom.predName)
        if mutex != None and any(mutex):
            blockName = "%s_" % gndatom.predName
            for i, v in enumerate(mutex):
                if v == False:
                    blockName += gndatom.params[i]
            if not blockName in self.gndBlocks:
                self.gndBlocks[blockName] = []
            self.gndBlocks[blockName].append(gndatom.idx)
            self.gndBlockLookup[gndatom.idx] = blockName
            
        # check the predicate for its type
        predicate = self.mln.pred_decls.get(gndatom.predName)
        blockname = predicate.getblockname(gndatom)
        gndblock = self.gndAtomicBlocks.get(blockname, None)
        if gndblock is None:
            gndblock = predicate.create_gndblock(blockname)
            self.gndAtomicBlocks[blockname] = gndblock
        gndblock.gndatoms.append(gndatom)
        self.gndAtom2AtomicBlock
        

    def _addGroundFormula(self, gndFormula, idxFormula, idxGndAtoms = None):
        '''
        Adds a ground formula to the MRF.

        - idxGndAtoms: indices of the ground atoms that are referenced by the 
        - formula (precomputed); If not given (None), will be determined automatically
        '''
        gndFormula.idxFormula = idxFormula
        self.gndFormulas.append(gndFormula)
        # update ground atom references
        if idxGndAtoms is None:
            idxGndAtoms = gndFormula.idxGroundAtoms()
        for idxGA in idxGndAtoms:
            self.gndAtomOccurrencesInGFs[idxGA].append(gndFormula)

    def removeGroundFormulaData(self):
        '''
        remove data on ground formulas to save space (e.g. because the necessary statistics were already collected and the actual formulas
        are no longer needed)
        '''
        del self.gndFormulas
        del self.gndAtomOccurrencesInGFs
#         del self.mln.gndFormulas
#         del self.mln.gndAtomOccurrencesInGFs
        if hasattr(self, "blockRelevantGFs"):
            del self.blockRelevantGFs

    def _addFormula(self, formula, weight):
        idxFormula = len(self.formulas)
        formula.weight = weight
        self.formulas.append(formula)
        return idxFormula

    def _setEvidence(self, idxGndAtom, value):
        self.evidence[idxGndAtom] = value

    def _setTemporaryEvidence(self, idxGndAtom, value):
        self.evidenceBackup[idxGndAtom] = self._getEvidence(idxGndAtom, closedWorld=False)
        self._setEvidence(idxGndAtom, value)

    def _getEvidence(self, idxGndAtom, closedWorld=True):
        '''
            gets the evidence truth value for the given ground atom or None if no evidence was given
            if closedWorld is True, False instead of None is returned
        '''
        v = self.evidence[idxGndAtom]
        if closedWorld and v is None:
            return 0
        return v

    def _clearEvidence(self):
        '''
        Erases the evidence in this MRF.
        '''
        self.evidence = [None] * len(self.gndAtoms)#dict([(i, None) for i in range(len(self.gndAtoms))])

    def getEvidenceDatabase(self):
        '''
        returns, from the current evidence list, a dictionary that maps ground atom names to truth values
        '''
        d = {}
        for idxGA, tv in enumerate(self.evidence):
            if tv != None:
                d[str(self.gndAtomsByIdx[idxGA])] = tv
        return d

    def printEvidence(self):
        for idxGA, value in enumerate(self.evidence):
            print "%s = %s" % (str(self.gndAtomsByIdx[idxGA]), '%2.2f' % value if value is not None else 'None')

    
    def getSoftEvidence(self):
        se = []
        for i, atom in self.gndAtomsByIdx.iteritems():
            truth = self.evidence[i]
            if truth > 0 and truth < 1:
                se.append({'expr': str(atom), 'p': truth})
        return se

#     def _getEvidenceTruthDegreeCW(self, gndAtom, worldValues):
#         '''
#             gets (soft or hard) evidence as a degree of belief from 0 to 1, making the closed world assumption,
#             soft evidence has precedence over hard evidence
#         '''
#         se = self._getSoftEvidence(gndAtom)
#         if se is not None:
#             if (1 == worldValues[gndAtom.idx] or None == worldValues[gndAtom.idx]):
#                 return se 
#             else: 
#                 return 1.0 - se # TODO allSoft currently unsupported
#         if worldValues[gndAtom.idx]:
#             return 1.0
#         else: return 0.0
# 
#     def _getEvidenceDegree(self, gndAtom):
#         '''
#             gets (soft or hard) evidence as a degree of belief from 0 to 1 or None if no evidence is given,
#             soft evidence takes precedence over hard evidence
#         '''
#         se = self._getSoftEvidence(gndAtom)
#         if se is not None:
#             return se
#         he = self._getEvidence(gndAtom.idx, False)
#         if he is None:
#             return None
#         if he == True:
#             return 1.0
#         else: return 0.0


#     def _getSoftEvidence(self, gndAtom):
#         '''
#         gets the soft evidence value (probability) for a given ground atom (or complex formula)
#         returns None if there is no such value
#         '''
#         s = strFormula(gndAtom)
#         for se in self.softEvidence: # TODO optimize
#             if se["expr"] == s:
#                 #print "worldValues[gndAtom.idx]", worldValues[gndAtom.idx]
#                 return se["p"]
#         return None
# 
#     def _setSoftEvidence(self, gndAtom, value):
#         s = strFormula(gndAtom)
#         for se in self.softEvidence:
#             if se["expr"] == s:
#                 se["p"] = value
#                 return

    def getTruthDegreeGivenSoftEvidence(self, gf, worldValues):
        cnf = gf.toCNF()
        prod = 1.0
        if isinstance(cnf, FirstOrderLogic.Conjunction):
            for disj in cnf.children:
                prod *= self._noisyOr(worldValues, disj)
        else:
            prod *= self._noisyOr(worldValues, cnf)
        return prod

    def _noisyOr(self, mln, worldValues, disj):
        if isinstance(disj, FirstOrderLogic.GroundLit):
            lits = [disj]
        elif isinstance(disj, FirstOrderLogic.TrueFalse):
            return disj.isTrue(worldValues)
        else:
            lits = disj.children
        prod = 1.0
        for lit in lits:
            p = mln._getEvidenceTruthDegreeCW(lit.gndAtom, worldValues)
            if not lit.negated:
                factor = p 
            else:
                factor = 1.0 - p
            prod *= 1.0 - factor
        return 1.0 - prod

    def _removeTemporaryEvidence(self):
        for idx, value in self.evidenceBackup.iteritems():
            self._setEvidence(idx, value)
        self.evidenceBackup.clear()

    def _isTrueGndFormulaGivenEvidence(self, gf):
        return gf.isTrue(self.evidence)

    def setEvidence(self, evidence, clear=True, cwAssumption=False):
        '''
        Sets the evidence, which is to be given as a dictionary that maps ground atom strings to their truth values.
        Any previous evidence is cleared.
        The closed-world assumption is applied to any predicates for which it was declared.
        If csAssumption is True, the closed-world assumption is applied to all non-evidence atoms.
        '''
        log = logging.getLogger(self.__class__.__name__)
        log.debug(self.evidence)
        if clear is True:
            self._clearEvidence()
        if cwAssumption:
            # apply closed world assumption
            log.info('Applying CW assumption...')
            self.evidence = [0] * len(self.gndAtoms)#map(lambda x: 0 if x is None else x, self.evidence)
            log.info('done.')
        log.info('Asserting evidence...')
        for gndAtom, value in evidence.iteritems():
            if not gndAtom in self.gndAtoms:
                log.debug('Evidence "%s=%s" is not among the ground atoms.' % (gndAtom, str(value)))
                continue
            idx = self.gndAtoms[gndAtom].idx
            self._setEvidence(idx, value)
            # If the value is true, set evidence for other vars in block (if any)
            # this is applicable only if the evidence if hard.
            if idx in self.gndBlockLookup:
                block = self.gndBlocks[self.gndBlockLookup[idx]]
                if value == 1:
                    for i in block:
                        if i != idx:
                            self._setEvidence(i, 0)
#         if cwAssumption:
#             # apply closed world assumption
#             log.info('Applying CW assumption')
#             self.evidence = map(lambda x: 0 if x is None else x, self.evidence)
        else:
            # handle closed-world predicates: Set all their instances that aren't yet known to false
            for pred in self.closedWorldPreds:
                log.debug('handling cw assumption for pred %s' % pred)
                if not pred in self.predicates or any(map(lambda d: len(self.domains[d]) == 0, self.mln.predicates[pred])): continue
                cwIndices = self._getPredGroundingsAsIndices(pred)
                for idxGA in cwIndices:
                    if self._getEvidence(idxGA, 0) == None:
                        self._setEvidence(idxGA, 0)

    def _getPllBlocks(self):
        '''
        creates an array self.pllBlocks that contains tuples (idxGA, block);
        one of the two tuple items is always None depending on whether the ground atom is in a block or not; 
        '''
        if hasattr(self, "pllBlocks"):
            return
        handledBlockNames = []
        self.pllBlocks = []
        for idxGA in range(len(self.gndAtoms)):
            if idxGA in self.gndBlockLookup:
                blockName = self.gndBlockLookup[idxGA]
                if blockName in handledBlockNames:
                    continue
                self.pllBlocks.append((None, self.gndBlocks[blockName]))
                handledBlockNames.append(blockName)
            else:
                self.pllBlocks.append((idxGA, None))

    def _getBlockRelevantGroundFormulas(self):
        '''
        computes the set of relevant ground formulas for each block
        '''
        mln = self
        self.blockRelevantGFs = [set() for _ in range(len(mln.pllBlocks))]
        for idxBlock, (idxGA, block) in enumerate(mln.pllBlocks):
            if block != None:
                for idxGA in block:
                    for gf in self.gndAtomOccurrencesInGFs[idxGA]:
                        self.blockRelevantGFs[idxBlock].add(gf)
            else:
                self.blockRelevantGFs[idxBlock] = self.gndAtomOccurrencesInGFs[idxGA]

    def _getBlockTrueone(self, block):
        idxGATrueone = -1
        for i in block:
            if self._getEvidence(i):
                if idxGATrueone != -1: 
                    raise Exception("More than one true ground atom in block %s!" % self._strBlock(block))
                idxGATrueone = i
                break
        if idxGATrueone == -1: raise Exception("No true gnd atom in block %s!" % self._strBlock(block))
        return idxGATrueone

    def _getBlockName(self, idxGA):
        return self.gndBlockLookup[idxGA]

    def _strBlock(self, block):
        return "{%s}" % (",".join(map(lambda x: str(self.gndAtomsByIdx[x]), block)))
    
    def _strBlockVar(self, varIdx):
        (idxGA, block) = self.pllBlocks[varIdx]
        if block is None:
            return str(self.gndAtomsByIdx[idxGA])
        else:
            return self._strBlock(block)

    def _getBlockExpsums(self, block, wt, world_values, idxGATrueone=None, relevantGroundFormulas=None):
        # if the true gnd atom in the block is not known (or there isn't one perhaps), set the first one to true by default and restore values later
        mustRestoreValues = False
        if idxGATrueone == None:
            mustRestoreValues = True
            backupValues = [world_values[block[0]]]
            world_values[block[0]] = True
            for idxGA in block[1:]:
                backupValues.append(world_values[idxGA])
                world_values[idxGA] = False
            idxGATrueone = block[0]
        # init sum of weights for each possible assignment of block
        # sums[i] = sum of weights for assignment where the block[i] is set to true
        sums = [0 for i in range(len(block))] 
        # process all (relevant) ground formulas
        checkRelevance = False
        if relevantGroundFormulas == None:
            relevantGroundFormulas = self.gndFormulas
            checkRelevance = True
        for gf in relevantGroundFormulas:
            # check if one of the ground atoms in the block appears in the ground formula
            if checkRelevance:
                isRelevant = False
                for i in block:
                    if i in gf.idxGroundAtoms():
                        isRelevant = True
                        break
                if not isRelevant: continue
            # make each one of the ground atoms in the block true once
            idxSum = 0
            for i in block:
                # set the current variable in the block to true
                world_values[idxGATrueone] = False
                world_values[i] = True
                # is the formula true?
                if gf.isTrue(world_values):
                    sums[idxSum] += wt[gf.idxFormula]
                # restore truth values
                world_values[i] = False
                world_values[idxGATrueone] = True
                idxSum += 1

        # if initialization values were used, reset them
        if mustRestoreValues:
            for i, value in enumerate(backupValues):
                world_values[block[i]] = value

        # return the list of exponentiated sums
        return map(exp, sums)

    def _getAtomExpsums(self, idxGndAtom, wt, world_values, relevantGroundFormulas=None):
        sums = [0, 0]
        # process all (relevant) ground formulas
        checkRelevance = False
        if relevantGroundFormulas == None:
            relevantGroundFormulas = self.gndFormulas
            checkRelevance = True
        old_tv = world_values[idxGndAtom]
        for gf in relevantGroundFormulas:
            if checkRelevance:
                if not gf.containsGndAtom(idxGndAtom):
                    continue
            for i, tv in enumerate([False, True]):
                world_values[idxGndAtom] = tv
                if gf.isTrue(world_values):
                    sums[i] += wt[gf.idxFormula]
                world_values[idxGndAtom] = old_tv
        return map(exp, sums)

    def _getAtom2BlockIdx(self):
        self.atom2BlockIdx = {}
        self.atom2ValueIdx = {}
        for idxBlock, (idxGA, block) in enumerate(self.pllBlocks):
            if block != None:
                for idxVal, idxGA in enumerate(block):
                    self.atom2BlockIdx[idxGA] = idxBlock
                    self.atom2ValueIdx[idxGA] = idxVal
            else:
                self.atom2BlockIdx[idxGA] = idxBlock
                self.atom2ValueIdx[idxGA] = 0

    def __createPossibleWorlds(self, values, idx, code, bit):
        if idx == len(self.gndAtoms):
            if code in self.worldCode2Index:
                raise Exception("Too many possible worlds") # this actually never happens because Python can handle "infinitely" long ints
            self.worldCode2Index[code] = len(self.worlds)
            self.worlds.append({"values": values})
            if len(self.worlds) % 1000 == 0:
                sys.stdout.write("%d\r" % len(self.worlds))
                pass
            return
        # values that can be set for the truth value of the ground atom with index idx
        possible_settings = [1, 0]
        # check if setting the truth value for idx is critical for a block 
        # (which is the case when idx is the highest index in a block)
        if idx in self.gndBlockLookup and POSSWORLDS_BLOCKING:
            block = self.gndBlocks[self.gndBlockLookup[idx]]
            if idx == max(block):
                # count number of true values already set
                nTrue, _ = 0, 0
                for i in block:
                    if i < len(values): # i has already been set
                        if values[i]:
                            nTrue += 1
                if nTrue >= 2: # violation, cannot continue
                    return
                if nTrue == 1: # already have a true value, must set current value to false
                    possible_settings.remove(1)
                if nTrue == 0: # no true value yet, must set current value to true
                    possible_settings.remove(0)
        # recursive descent
        for x in possible_settings:
            if x: offset = bit
            else: offset = 0
            self.__createPossibleWorlds(values + [x], idx + 1, code + offset, bit << 1)

    def _createPossibleWorlds(self):
        self.worldCode2Index = {}
        self.worlds = []
        self.__createPossibleWorlds([], 0, 0, 1)

    def getWorld(self, worldNo):
        '''
            gets the possible world with the given one-based world number
        '''
        self._getWorlds()
        return self.worlds[worldNo - 1]

    def _getWorlds(self):
        '''
            creates the set of possible worlds and calculates for each world all the necessary values
        '''
        if not hasattr(self, "worlds"):
            self._createPossibleWorlds()
            if self.mln.parameterType == 'weights':
                self._calculateWorldValues()
            elif self.mln.parameterType == 'probs':
                self._calculateWorldValues_prob()

    def _calculateWorldValues(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for worldIndex, world in enumerate(self.worlds):
            weights = []
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    weights.append(wts[gndFormula.idxFormula])
            exp_sum = exp(sum(weights))
            if self.mln.learnWtsMode != 'LL_ISE' or self.mln.allSoft == True or worldIndex != self.idxTrainingDB:
                total += exp_sum
            world["sum"] = exp_sum
            world["weights"] = weights
        self.partition_function = total

    def _calculateWorldExpSum(self, world, wts=None):
        if wts is None:
            wts = self._weights()
        sum = 0
        for gndFormula in self.gndFormulas:
            if self._isTrue(gndFormula, world):
                sum += wts[gndFormula.idxFormula]
        return exp(sum)

    def _countNumTrueGroundingsInWorld(self, idxFormula, world):
        numTrue = 0
        for gf in self.gndFormulas:
            if gf.idxFormula == idxFormula:
                if self._isTrue(gf, world["values"]):
                    numTrue += 1
        return numTrue

    def countWorldsWhereFormulaIsTrue(self, idxFormula):
        '''
        Counts the number of true groundings in each possible world and outputs a report
        with (# of true groundings, # of worlds with that number of true groundings).
        '''
        counts = {}
        for world in self.worlds:
            numTrue = self._countNumTrueGroundingsInWorld(idxFormula, world)
            old_cnt = counts.get(numTrue, 0)
            counts[numTrue] = old_cnt + 1
        print counts

    def countTrueGroundingsForEachWorld(self, appendToWorlds=False):
        '''
        Returns array of array of int a with a[i][j] = number of true groundings of j-th formula in i-th world
        '''
        all = []
        self._getWorlds()
        for world in self.worlds:
            counts = self.countTrueGroundingsInWorld(world["values"])
            all.append(counts)
            if appendToWorlds:
                world["counts"] = counts
        return all

    def countTrueGroundingsInWorld(self, world):
        '''
            computes the number of true groundings of each formula for the given world
            returns a vector v, where v[i] = number of groundings of the i-th MLN formula
        '''
        import numpy
        formulaCounts = numpy.zeros(len(self.mln.formulas), numpy.float64)                
        for gndFormula in self.mrf.mln.gndFormulas:
            if self._isTrue(gndFormula, world):
                formulaCounts[gndFormula.idxFormula] += 1
        return formulaCounts

    def _calculateWorldValues2(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for world in self.worlds:
            prob = 1.0
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    prob *= wts[gndFormula.idxFormula]
                else:
                    prob *= (1 - wts[gndFormula.idxFormula])
            world["prod"] = prob
            total += prob
        self.partition_function = total

    def _calculateWorldValues_prob(self, wts=None):
        if wts == None:
            wts = self._weights()
        total = 0
        for world in self.worlds:
            prod = 1.0
            for gndFormula in self.gndFormulas:
                if self._isTrue(gndFormula, world["values"]):
                    prod *= wts[gndFormula.idxFormula]
            world["prod"] = prod
            total += prod
        self.partition_function = total

    def _toCNF(self, allPositive=False):
        '''
            converts all ground formulas to CNF and also makes changes to the
            MLN's set of formulas, such that the correspondence between groundings
            and formulas still holds
        '''
        self.gndFormulas, self.formulas = toCNF(self.gndFormulas, self.formulas, logic=self.mln.logic)

    def _isTrue(self, gndFormula, world_values):
        return gndFormula.isTrue(world_values)

    def printGroundFormulas(self, weight_transform=lambda x: x):
        for gf in self.gndFormulas:
            print "%7.3f  %s" % (weight_transform(self.formulas[gf.idxFormula].weight), strFormula(gf))
    
    def getGroundFormulas(self):
        '''
            returns a list of pairs (w, gf)
        '''
        return [(self.formulas[gf.idxFormula].weight, gf) for gf in self.gndFormulas]

    def printGroundAtoms(self):
        l = self.gndAtoms.keys()
        l.sort()
        for ga in l:
            print ga
            
    def strGroundAtom(self, idx):
        return str(self.gndAtomsByIdx[idx])

    def printState(self, world_values, showIndices=False):
        for idxGA, block in self.pllBlocks:
            if idxGA != None:
                if showIndices: print "%-5d" % idxGA,
                print "%s=%s" % (str(self.gndAtomsByIdx[idxGA]), str(world_values[idxGA]))
            else:
                trueone = -1
                for i in block:
                    if world_values[i]:
                        trueone = i
                        break
                print "%s=%s" % (self._strBlock(block), str(self.gndAtomsByIdx[trueone]))

    # prints relevant data (including the entire state) for the given world (list of truth values) on a single line
    # for details see printWorlds
    def printWorld(self, world, mode=1, format=1):
        if "weights" in world and world["weights"] == []:
            world["weights"] = [0.0]
        literals = []
        for idx in range(len(self.gndAtoms)):
            if idx in self.gndBlockLookup: # process all gnd atoms in blocks in one go and only print the one that's true
                block = self.gndBlocks[self.gndBlockLookup[idx]]
                if idx == min(block): # process each block only once
                    maxlen = 0
                    gndAtom = None
                    for i in block:
                        maxlen = max(maxlen, len(str(self.gndAtomsByIdx[i])))
                        if world["values"][i]:
                            gndAtom = self.gndAtomsByIdx[i]
                    literal = "%-*s" % (maxlen, str(gndAtom))
                else:
                    continue
            else:
                gndAtom = str(self.gndAtomsByIdx[idx])
                value = world["values"][idx]
                literal = {True: " ", False:"!"}[value] + gndAtom
            literals.append(literal)
        if mode == 1:
            prob = world["sum"] / self.partition_function
            weights = "<- " + " ".join(map(lambda s: "%.1f" % s, world["weights"]))
            if format == 1: print "%6.2f%%  %s  %e <- %.2f %s" % (100 * prob, " ".join(literals), world["sum"], sum(world["weights"]), weights)
            elif format == 2: print "%6.2f%%  %s  %s" % (100 * prob, " ".join(literals), str(world["counts"]))
            #print "Pr=%.2f  %s  %15.0f" % (prob, " ".join(literals), world["sum"])
        elif mode == 2:
            print "%6.2f%%  %s  %.2f" % (100 * world["prod"] / self.partition_function, " ".join(literals), world["prod"])
        elif mode == 3:
            print " ".join(literals)

    # prints all the possible worlds implicitly defined by the set of constants with which the MLN was combined
    # Must call combine or combineDB beforehand if the MLN does not define at least one constant for every type/domain
    # The list contains for each world its 1-based index, its probability, the (conjunction of) literals, the exponentiated
    # sum of weights, the sum of weights and the individual weights that applied
    def printWorlds(self, sort=False, mode=1, format=1):
        self._getWorlds()
        if sort:
            worlds = list(self.worlds)
            worlds.sort(key=lambda x:-x["sum"])
        else:
            worlds = self.worlds
        print
        k = 1
        for world in worlds:
            print "%*d " % (int(ceil(log(len(self.worlds)) / log(10))), k),
            self.printWorld(world, mode=mode, format=format)
            k += 1
        print "Z = %f" % self.partition_function

    # prints the worlds where the given formula (condition) is true (otherwise same as printWorlds)
    def printWorldsFiltered(self, condition, mode=1, format=1):
        condition = self.logic.parseFormula(condition).ground(self, {})
        self._getWorlds()
        k = 1
        for world in self.worlds:
            if condition.isTrue(world["values"]):
                print "%*d " % (int(ceil(log(len(self.worlds)) / log(10))), k),
                self.printWorld(world, mode=mode, format=format)
                k += 1

    # prints the num worlds with the highest probability
    def printTopWorlds(self, num=10, mode=1, format=1):
        self._getWorlds()
        worlds = list(self.worlds)
        worlds.sort(key=lambda w:-w["sum"])
        for i in range(min(num, len(worlds))):
            self.printWorld(worlds[i], mode=mode, format=format)

    # prints, for the given world, the probability, the literals, the sum of weights, plus for each ground formula the truth value on a separate line
    def printWorldDetails(self, world):
        self.printWorld(world)
        for gf in self.gndFormulas:
            isTrue = gf.isTrue(world["values"])
            print "  %-5s  %f  %s" % (str(isTrue), self.formulas[gf.idxFormula].weight, strFormula(gf))

    def printFormulaProbabilities(self):
        self._getWorlds()
        sums = [0.0 for _ in range(len(self.formulas))]
        totals = [0.0 for i in range(len(self.formulas))]
        for world in self.worlds:
            for gf in self.gndFormulas:
                if self._isTrue(gf, world["values"]):
                    sums[gf.idxFormula] += world["sum"] / self.partition_function
                totals[gf.idxFormula] += world["sum"] / self.partition_function
        for i, formula in enumerate(self.formulas):
            print "%f %s" % (sums[i] / totals[i], str(formula))

    def printExpectedNumberOfGroundings(self):
        '''
            prints the expected number of true groundings of each formula
        '''
        self._getWorlds()
        counts = [0.0 for i in range(len(self.formulas))]
        for world in self.worlds:
            for gf in self.gndFormulas:
                if self._isTrue(gf, world["values"]):
                    counts[gf.idxFormula] += world["sum"] / self.partition_function
        #print counts
        for i, formula in enumerate(self.formulas):
            print "%f %s" % (counts[i], str(formula))

    def _fitProbabilityConstraints(self, probConstraints, fittingMethod=InferenceMethods.Exact, 
                                   fittingThreshold=1.0e-3, fittingSteps=20, fittingMCSATSteps=5000, 
                                   fittingParams=None, given=None, queries=None, verbose=True, 
                                   maxThreshold=None, greedy=False, probabilityFittingResultFileName=None, **args):
        '''
            applies the given probability constraints (if any), dynamically 
            modifying weights of the underlying MLN by applying iterative proportional fitting

            probConstraints: list of constraints
            inferenceMethod: one of the inference methods defined in InferenceMethods
            inferenceParams: parameters to pass on to the inference method
            given: if not None, fit parameters of posterior (given the evidence) rather than prior
            queries: queries to compute along the way, results for which will be returned
            threshold:
                when maximum absolute difference between desired and actual probability drops below this value, then stop (convergence)
            maxThreshold:
                if not None, then convergence is relaxed, and we stop when the *mean* absolute difference between desired and
                actual probability drops below "threshold" *and* the maximum is below "maxThreshold"
        '''
        inferenceMethod = fittingMethod
        threshold = fittingThreshold
        maxSteps = fittingSteps
        if fittingParams is None:
            fittingParams = {}
        inferenceParams = fittingParams
        inferenceParams["doProbabilityFitting"] = False # avoid recursive fitting calls when calling embedded inference method
        if given == None:
            given = ""
        if queries is None:
            queries = []
        if inferenceParams is None:
            inferenceParams = {}
        if len(probConstraints) == 0:
            if len(queries) > 0:
                pass # TODO !!!! because this is called from inferIPFPM, should perform inference anyhow
            return
        if verbose:
            print "applying probability fitting...(max. deviation threshold:", fittingThreshold, ")"
        t_start = time.time()

        # determine relevant formulas
        for req in probConstraints:
            # if we don't yet have a ground formula to fit, create one
            if not "gndFormula" in req:
                # if we don't yet have a formula to use, search for one that matches the expression to fit
                if not "idxFormula" in req:
                    idxFormula = None
                    for idxF, formula in enumerate(self.formulas):
                        #print strFormula(formula), req["expr"]
                        if strFormula(formula).replace(" ", "") == req["expr"]:
                            idxFormula = idxF
                            break
                    if idxFormula is None:
                        raise Exception("Probability constraint on '%s' cannot be applied because the formula is not part of the MLN!" % req["expr"])
                    req["idxFormula"] = idxFormula
                # instantiate a ground formula
                formula = self.formulas[req["idxFormula"]]
                variables = formula.getVariables(self)
                groundVars = {}
                for varName, domName in variables.iteritems(): # instantiate vars arbitrarily (just use first element of domain)
                    groundVars[varName] = self.domains[domName][0]
                gndFormula = formula.ground(self, groundVars)
                req["gndExpr"] = str(gndFormula)
                req["gndFormula"] = gndFormula

        # iterative fitting algorithm
        step = 1 # fitting round
        fittingStep = 1 # actual IPFP iteration
        #print "probConstraints", probConstraints, "queries", queries
        what = [r["gndFormula"] for r in probConstraints] + queries
        done = False
        while step <= maxSteps and not done:
            # calculate probabilities of the constrained formulas (ground formula)
            if inferenceMethod == InferenceMethods.Exact:
                if not hasattr(self, "worlds"):
                    self._getWorlds()
                else:
                    self._calculateWorldValues()
                results = self.inferExact(what, given=given, verbose=False, **inferenceParams)
            elif inferenceMethod == InferenceMethods.EnumerationAsk:
                results = self.inferEnumerationAsk(what, given=given, verbose=False, **inferenceParams)
            #elif inferenceMethod == InferenceMethods.ExactLazy:
            #    results = self.inferExactLazy(what, given=given, verbose=False, **inferenceParams)
            elif inferenceMethod == InferenceMethods.MCSAT:
                results = self.inferMCSAT(what, given=given, verbose=False, maxSteps = fittingMCSATSteps, **inferenceParams)
            else:
                raise Exception("Requested inference method (%s) not supported by probability constraint fitting" % InferenceMethods.getName(inferenceMethod))
            if type(results) != list:
                results = [results]
            # compute deviations
            diffs = [abs(r["p"] - results[i]) for (i, r) in enumerate(probConstraints)]
            maxdiff = max(diffs)
            meandiff = sum(diffs) / len(diffs)
            # are we done?
            done = maxdiff <= threshold
            if not done and maxThreshold is not None: # relaxed convergence criterion
                done = (meandiff <= threshold) and (maxdiff <= maxThreshold)
            if done:
                if verbose: print "  [done] dev max: %f mean: %f" % (maxdiff, meandiff)
                break
            # select constraint to fit
            if greedy:
                idxConstraint = diffs.index(maxdiff)
                strStep = "%d;%d" % (step, fittingStep)
            else:
                idxConstraint = (fittingStep - 1) % len(probConstraints)
                strStep = "%d;%d/%d" % (step, idxConstraint + 1, len(probConstraints))
            req = probConstraints[idxConstraint]
            # get the scaling factor and apply it
            formula = self.formulas[req["idxFormula"]]
            p = results[idxConstraint]
            #print "p", p, "results", results, "idxConstraint", idxConstraint
            pnew = req["p"]
            precision = 1e-3
            if p == 0.0: p = precision
            if p == 1.0: p = 1 - precision
            f = pnew * (1 - p) / p / (1 - pnew)
            old_weight = formula.weight
            formula.weight += float(logx(f)) #make sure to set the weight to a native float and not an mpmath value
            diff = diffs[idxConstraint]
            # print status
            if verbose: print "  [%s] p=%f vs. %f (diff = %f), weight %s: %f -> %f, dev max %f mean %f, elapsed: %.3fs" % (strStep, p, pnew, diff, strFormula(formula), old_weight, formula.weight, maxdiff, meandiff, time.time() - t_start)
            if fittingStep % len(probConstraints) == 0:
                step += 1
            fittingStep += 1

        #write resulting mln:
        if probabilityFittingResultFileName != None:
            mlnFile = file(probabilityFittingResultFileName, "w")
            self.mln.write(mlnFile)
            mlnFile.close()
            print "written MLN with probability constraints to:", probabilityFittingResultFileName

        return (results[len(probConstraints):], {"steps": min(step, maxSteps), "fittingSteps": fittingStep, "maxdiff": maxdiff, "meandiff": meandiff, "time": time.time() - t_start})

    #
    # TODO: Move the inference into MLN. It should be the only class 
    #       a user has to interface.
    #

    def infer(self, what, given=None, verbose=True, **args):
        '''
        Infer a probability P(F1 | F2) where F1 and F2 are formulas - using the default inference method specified for this MLN
        what: a formula, e.g. "foo(A,B)", or a list of formulas
        given: either
                 * another formula, e.g. "bar(A,B) ^ !baz(A,B)"
                   Note: it can be an arbitrary formula only for exact inference, otherwise it must be a conjunction
                   This will overwrite any evidence previously set in the MLN
                 * None if the evidence currently set in the MLN is to be used
        verbose: whether to print the results
        args: any additional arguments to pass on to the actual inference method
        '''
        # call actual inference method
        defaultMethod = self.mln.defaultInferenceMethod
        if defaultMethod == InferenceMethods.Exact:
            return self.inferExact(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.GibbsSampling:
            return self.inferGibbs(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.MCSAT:
            return self.inferMCSAT(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.FuzzyMCSAT:
            return self.inferFuzzyMCSAT(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.IPFPM_exact:
            return self.inferIPFPM(what, given, inferenceMethod=InferenceMethods.Exact, **args)
        elif defaultMethod == InferenceMethods.IPFPM_MCSAT:
            return self.inferIPFPM(what, given, inferenceMethod=InferenceMethods.MCSAT, **args)
        elif defaultMethod == InferenceMethods.EnumerationAsk:
            return self.inferEnumerationAsk(what, given, verbose=verbose, **args)
        elif defaultMethod == InferenceMethods.WCSP:
            return self.inferWCSP(what, given, verbose, **args)
        elif defaultMethod == InferenceMethods.BnB:
            return self.inferBnB(what, given, verbose, **args)
        else:
            raise Exception("Unknown inference method '%s'. Use a member of InferenceMethods!" % str(self.defaultInferenceMethod))

    def inferExact(self, what, given=None, verbose=True, **args):
        return self._infer(ExactInference(self), what, given, verbose, **args)

    def inferExactLinear(self, what, given=None, verbose=True, **args):
        return self._infer(ExactInferenceLinear(self), what, given, verbose, **args)

    def inferEnumerationAsk(self, what, given=None, verbose=True, **args):
        return self._infer(EnumerationAsk(self), what, given, verbose, **args)

    def inferGibbs(self, what, given=None, verbose=True, **args):
        return self._infer(GibbsSampler(self), what, given, verbose=verbose, **args)

    def inferMCSAT(self, what, given=None, verbose=True, **args):
        mcsat = MCSAT(self, verbose=verbose) # can be used for later data retrieval
        return self._infer(mcsat, what, given, verbose, **args)
    
    def inferFuzzyMCSAT(self, what, given=None, verbose=True, **args):
        return self._infer(FuzzyMCSAT(self), what, given, verbose, **args)

    def inferIPFPM(self, what, given=None, verbose=True, **args):
        '''
            inference based on the iterative proportional fitting procedure at the model level (IPFP-M)
        '''
        ipfpm = IPFPM(self) # can be used for later data retrieval
        return self._infer(ipfpm, what, given, verbose, **args)
    
    def inferWCSP(self, what, given=None, verbose=True, **args):
        '''
        Perform WCSP (MPE) inference on the MLN.
        '''
        return self._infer(WCSPInference(self), what, given, verbose, **args)
    
    def inferBnB(self, what, given=None, verbose=True, **args):
        return self._infer(BnBInference(self), what, given, verbose, **args)

    def _infer(self, inferObj, what, given=None, verbose=True, doProbabilityFitting=True, **args):
        # if there are prior probability constraints, apply them first
        if len(self.probreqs) > 0 and doProbabilityFitting:
            fittingParams = {
                "fittingMethod": self.mln.probabilityFittingInferenceMethod,
                "fittingSteps": self.mln.probabilityFittingMaxSteps,
                "fittingThreshold": self.mln.probabilityFittingThreshold,
                "probabilityFittingResultFileName": None
                #fittingMCSATSteps
            }
            fittingParams.update(args)
            self._fitProbabilityConstraints(self.probreqs, **fittingParams)
        # run actual inference method
        self.inferObj = inferObj
        return inferObj.infer(what, given, verbose=verbose, **args)

    def getResultsDict(self):
        '''
            gets the results computed by the last call to an inference method (infer*)
            in the form of a dictionary that maps ground formulas to probabilities
        '''
        return self.inferObj.getResultsDict()

    def _weights(self):
        ''' returns the weight vector as a list '''
        return [f.weight for f in self.formulas]
    
    def getRandomWorld(self):
        ''' uniformly samples from the set of possible worlds (taking blocks into account) '''
        self._getPllBlocks()
        state = [None] * len(self.gndAtoms)
        for _, (idxGA, block) in enumerate(self.pllBlocks):
            if block != None: # block of mutually exclusive atoms
                chosen = block[random.randint(0, len(block) - 1)]
                for idxGA in block:
                    state[idxGA] = (idxGA == chosen)
            else: # regular ground atom, which can either be true or false
                chosen = random.randint(0, 1)
                state[idxGA] = bool(chosen)
        return state

    def domSize(self, domName):
        return len(self.domains[domName])

    def writeDotFile(self, filename):
        '''
        write a .dot file for use with GraphViz (in order to visualize the current ground Markov network)
        '''
        if not hasattr(self, "gndFormulas") or len(self.gndFormulas) == 0:
            raise Exception("Error: cannot create graph because the MLN was not combined with a concrete domain")
        f = file(filename, "wb")
        f.write("graph G {\n")
        graph = {}
        for gf in self.gndFormulas:
            idxGndAtoms = gf.idxGroundAtoms()
            for i in range(len(idxGndAtoms)):
                for j in range(i + 1, len(idxGndAtoms)):
                    edge = [idxGndAtoms[i], idxGndAtoms[j]]
                    edge.sort()
                    edge = tuple(edge)
                    if not edge in graph:
                        f.write("  ga%d -- ga%d\n" % edge)
                        graph[edge] = True
        for gndAtom in self.gndAtoms.values():
            f.write('  ga%d [label="%s"]\n' % (gndAtom.idx, str(gndAtom)))
        f.write("}\n")
        f.close()

    def writeGraphML(self, filename):
        import graphml  # @UnresolvedImport
        G = graphml.Graph()
        nodes = []
        for i in xrange(len(self.gndAtomsByIdx)):
            ga = self.gndAtomsByIdx[i]
            nodes.append(graphml.Node(G, label=str(ga), shape="ellipse", color=graphml.randomVariableColor))
        links = {}
        for gf in self.gndFormulas:
            print gf
            idxGAs = sorted(gf.idxGroundAtoms())
            for idx, i in enumerate(idxGAs):
                for j in idxGAs[idx+1:]:
                    t = (i,j)
                    if not t in links:
                        print "  %s -- %s" % (nodes[i], nodes[j])
                        graphml.UndirectedEdge(G, nodes[i], nodes[j])
                        links[t] = True
        f = open(filename, "w")
        G.write(f)
        f.close()
