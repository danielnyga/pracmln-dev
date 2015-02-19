# 
#
# (C) 2011-2015 by Daniel Nyga (nyga@cs.uni-bremen.de)
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
from mln.learning.common import AbstractLearner
from collections import defaultdict
from mln.learning.cll import CLL
import numpy as np
from utils import StopWatch, dict_subset
import logging
from experimental.adaboost import weighted_linear_regression
import math
from mln.grounding.default import EqualityConstraintGrounder
from logic.common import Logic
from tabulate import tabulate
from utils.clustering import CorrelationClustering
from mln.util import strFormula


class AtomCorrelationMatrix(object):
    '''
    Matrix of correlations of atoms within a formula.
    '''
    
    def __init__(self, mlnboost, formula, group_templ_atoms=False):
        '''
        group_templ_atoms:     do not compute the correlations of atoms
                               that have been generated from the same template.
        '''
        self.mlnboost = mlnboost
        self.mln = mlnboost.mln
        self.bmrfs = mlnboost.bmrfs
        self.formula = formula
        self.groups = {} # maps an atom to its template
        if group_templ_atoms:
            atoms = []
            for literal in formula.iterLiterals():
                for templ in literal.getTemplateVariants(self.mln):
                    atoms.append(templ)
                    self.groups[templ] = literal
        else:
            atoms = formula.getTemplateAtoms(self.mln)
        self.atoms = sorted(atoms, key=str)
        self.atom2idx = dict([(a, i) for a, i in enumerate(self.atoms)])
        self.corr = defaultdict(dict)
        eq_constraints = formula.getAtomicConstituents(ofType=Logic.Equality)
        for i in range(len(self.atoms)):
            for j in range(i + 1):
                templ1 = self.groups.get(self.atoms[i])
                templ2 = self.groups.get(self.atoms[j]) 
                if templ1 is not None and templ2 is not None and templ1 is templ2:
                    self.corr[i][j] = None
                else:
                    self.corr[i][j] = self._compute_atom_correlation(self.atoms[i], self.atoms[j], eq_constraints)
                
    def __getitem__(self, (i, j)):
        if isinstance(i, Logic.Lit):
            i = self.atom2idx[i]
        if isinstance(j, Logic.Lit):
            j = self.atom2idx[j]
        return self.corr[i][j] if i > j else self.corr[j][i]
    
    def __str__(self):
        table = [[str(self.atoms[i])] + [self[i,j] for j in range(len(self.atoms))] for i in range(len(self.atoms))]
        return tabulate(table, headers=map(str, self.atoms))
    
    def __len__(self):
        return len(self.atoms)
        
    def iteritems(self):
        for i in range(len(self.atoms)):
            for j in range(i + 1):
                if self[i, j] is None: continue
                yield (self.atoms[i], self.atoms[j]), self[i, j]
                
    def items(self):
        return list(self.iteritems())
        
        
    def _compute_atom_correlation(self, atom1, atom2, *eq_constraints):
        '''
        Computes the (weighted) correlation of two atoms with respect
        to truth values of all their ground atoms in all learning databases.
        
        Example: corr(foo(?x,X), bar(?x,Y)) is computed by the correlation
                 of all ground atoms that can be generated by substituting
                 ?x in all databases. Weights of single ground atoms are
                 taken into account. 
        eq_constraints is an optional argument specifying a list of equality
        constraints on variables contained in atom1 or atom2 that have to be
        met by the ground atoms taken into account when computing the covariances. 
        '''
        # construct a conjunction for counting covariances
        conj = self.mln.logic.conjunction([atom1, atom2])
        ecg = EqualityConstraintGrounder(self.mln, EqualityConstraintGrounder.getVarDomainsFromFormula(self.mln, conj))
        valid_varassignments = list(ecg.iter_true_variable_assignments())
        # first, compute the (weighted) sample means
        w1_total = w2_total = w2_true = w1_true = 0.
        datapoints = [] # stores tuples (truth1, truth2, w1, w2) for later covariance computation
        for bmrf in self.bmrfs:
            for varassign in conj.iterVariableAssignments(bmrf.mrf):
                if not any([dict_subset(valid, varassign) for valid in valid_varassignments]):
                    continue
                gconj = conj.ground(bmrf.mrf, varassign)
                (gndlit1, gndlit2) = gconj.children
                w1 = bmrf.bgnd_atoms[gndlit1.gndAtom.idx].weight
                w2 = bmrf.bgnd_atoms[gndlit2.gndAtom.idx].weight
                w1_true += gndlit1.isTrue(bmrf.mrf.evidence) * w1 
                w2_true += gndlit2.isTrue(bmrf.mrf.evidence) * w2
                w1_total += w1
                w2_total += w2
                datapoints.append((gndlit1.isTrue(bmrf.mrf.evidence), gndlit2.isTrue(bmrf.mrf.evidence), w1, w2))
        mean1 = w1_true / w1_total
        mean2 = w2_true / w2_total
        # second, compute the weighted variances and covariances
        w_total = wsq_total = cov = var1 = var2 = 0.0
        for (t1, t2, w1, w2) in datapoints:
            var1 += (t1 - mean1) ** 2 * w1
            var2 += (t2 - mean2) ** 2 * w2
            w = w1 * w2
            w_total += w
            wsq_total += w ** 2
            cov += w * (mean1 - t1) * (mean2 - t2)
        var1 /= ((len(datapoints) - 1) / float(len(datapoints))) * w1_total
        var2 /= ((len(datapoints) - 1) / float(len(datapoints))) * w2_total
        return w_total / (w_total ** 2 - wsq_total) * cov / math.sqrt(var1 * var2)


class WeakMLNLearn():
    '''
    Weight-sensitive learning of 'weak' Markov logic network structures.
    '''
    
    def __init__(self, mlnboost):
        self.mln = mlnboost.mln
        self.mlnboost = mlnboost
        
    def learn(self):
        formulas = []
        for f in self.mln.formulas:
            formulas.extend(self._learn_from_formula(f))
        for i, f in enumerate(formulas):
            f.idxFormula = i
            f.weight = 0
            f.isHard = False
        return formulas
        
    def _learn_from_formula(self, from_formula):
        corr = AtomCorrelationMatrix(self.mlnboost, from_formula, group_templ_atoms=True)
        clusters = CorrelationClustering(corr.items(), corr.atoms, thr=None).cluster2data
        formulas = []
        for cluster in clusters.values():
            formulas.extend(self._formula_from_cluster(cluster, corr))
        return formulas
        
    def _formula_from_cluster(self, cluster_atoms, corr):
        # group atoms by their template
        atom_groups = defaultdict(list)
        for atom in cluster_atoms:
            atom_groups[corr.groups[atom]].append(atom)
        cnf = []
        for disj in atom_groups.values():
            if len(disj) == 1:
                cnf.append(self.mln.logic.lit(False, disj[0].predName, disj[0].params))
            else:
                cnf.append(self.mln.logic.disjunction(disj))
        if len(cnf) == 1:
            return [cnf[0]]
        else:
            return [self.mln.logic.conjunction(cnf)]


class MLNBoost(AbstractLearner):
    '''
    Learning MLNs via functional gradient boosting.
    '''
    
    def __init__(self, mln, dbs, **params):
        AbstractLearner.__init__(self, mln, mrf=None, **params)
        self.dbs = dbs
        self.clock = StopWatch()
    
    def _prepareOpt(self):
        self.cll_learners = [] # list of all CLL learners
        self.gndatoms = [] # list of all boosted ground atoms
        self.bmrfs = []
        #  generate the template atoms from the literals in all formula.
#         self._generate_templ_atoms()
        mln = self.mln
        self.clock.tag('grounding all MRFs', False)
        for db in self.dbs:
            mrf = mln.groundMRF(db, cwAssumption=True, groundingMethod='NoGroundingFactory', **self.params)
            cll = CLL(mln, mrf, partSize=1)
            self.cll_learners.append(cll)
            cll._prepareOpt()
            bmrf = MLNBoost.BoostedMRF(mrf)
            self.bmrfs.append(bmrf)
            for partition in cll.partitions:
                for gndatom in partition.variables[0].gndatoms:
                    bgndatom = MLNBoost.BoostedGroundAtom(gndatom, len(self.gndatoms), mrf.evidence[gndatom.idx], 
                                                          1. / partition.getNumberOfPossibleWorlds(), 1, mrf, cll)
                    self.gndatoms.append(bgndatom)
                    bmrf.bgnd_atoms[gndatom.idx] = bgndatom
        self.clock.finish()
    
    
    def run(self, **params):
        log = logging.getLogger(self.__class__.__name__)
        self._prepareOpt()
        
        formula_weights = []#np.zeros(len(self.mln.formulas))
        T = params.get('maxiter')
        if T is None: T = 5
        formulas = []
        for t in range(T):
            print 'MLN-BOOST ITERATION #%s / %d' % (str(t+1).rjust(3, ' '), T)
            weak_formulas = WeakMLNLearn(self).learn()
            weakmln = self.mln.duplicate()
            weakmln.formulas = weak_formulas
            weakmln = weakmln.materializeFormulaTemplates(self.dbs)
            for i, f in enumerate(weak_formulas):
                f.idxFormula = i
                print strFormula(f)
            formulas.extend(weak_formulas)
            # ground the weak MLN and adjust the cll learners
            self.cll_learners = [] # list of all CLL learners
            for i, _ in enumerate(self.dbs):
                mrf = self.bmrfs[i].mrf
                cll = CLL(weakmln, mrf, partSize=1)
                self.cll_learners.append(cll)
                cll._prepareOpt()
                cll._computeStatistics()
                for partition in cll.partitions:
                    for gndatom in partition.variables[0].gndatoms:
                        bgndatom = self.bmrfs[i].bgnd_atoms[gndatom.idx]
                        bgndatom.set_cll(cll)
            
            # compute the targets
            self.clock.tag('computing the regression targets')
            y = [-(gndatom.truth - gndatom.prob) / (gndatom.prob * (1. - gndatom.prob)) for gndatom in self.gndatoms]
            if len(filter(lambda x: float('inf') == x or float('inf') == -x, y)) > 0:
                log.error('Learning has stopped due to numerical instability.')
                break
            self.clock.finish()
            # compute the weights
            total = 0
            for gndatom in self.gndatoms:
                gndatom.weight = gndatom.prob * (1. - gndatom.prob)
                total += gndatom.weight
            for a in self.gndatoms:
                a.weight /= total
            # construct the design matrix
            self.clock.tag('constructing the design matrix')
            designmat = np.zeros((len(self.gndatoms), len(weakmln.formulas)))
            for gndatom in self.gndatoms:
                stat = gndatom.cll.statistics
                cll = gndatom.cll
                for f_idx in cll.partRelevantFormulas[gndatom.partition_idx]: # collect all statistics from formulas that are relevant for this gnd atom
                    negvalues = sum([v for v, i in enumerate(stat[f_idx][gndatom.partition_idx]) if i != gndatom.value_idx])
                    print negvalues
                    posvalue = stat[f_idx][gndatom.partition_idx][gndatom.value_idx]
                    print posvalue
                    designmat[gndatom.idx, f_idx] = negvalues - posvalue
#             for r in designmat:
#                 print r
            # do the regression
            self.clock.tag('linear regression')
            f_weights = weighted_linear_regression(y, designmat, [atom.weight for atom in self.gndatoms])
            f_weights *= .5
            formula_weights.extend(f_weights)
            self.clock.finish()
            # update the model predictions
            probabilities = {}
            for cll in self.cll_learners:
                probabilities[cll] = cll._computeProbabilities(f_weights)
            for gndatom in self.gndatoms:
                probs = probabilities[gndatom.cll]
                gndatom.prob = probs[gndatom.partition_idx][gndatom.value_idx]
        for gndatom in self.gndatoms:
            print '%.3f  %.3f  %s' % (gndatom.truth, gndatom.prob, str(gndatom.atom))
        self.clock.printSteps()
        self.mln.formulas = formulas
        for f, w in zip(formulas, formula_weights):
            f.isHard = False
            f.weight = w
        self.mln = self.mln.materializeFormulaTemplates(self.dbs)
        return formula_weights
    
    
    @staticmethod
    def replace_template_variables(mln, formula):
        vars = formula._getTemplateVariables(mln)
        for i, var in enumerate(vars):
            formula = formula._groundTemplate({var: '?var_%d' % i})[0]
        return formula


    @staticmethod
    def merge_attribute_domains(mln, *dbs):
        attr_domains = defaultdict(set)
        for db in dbs:
            for dom, values in db.domains.iteritems():
                if dom.startswith(':'): continue
                attr_domains[dom].update(values)
        return attr_domains
    
    def _generate_templ_atoms(self):
        processed = set()
        templ_atoms = []
        for formula in self.mln.formulas:
            for literal in formula.iterLiterals():
                for templ in literal.getTemplateVariants(self.mln):
                    if str(templ) not in processed:
                        processed.add(str(templ))
                        templ_atoms.append(templ)
        self.templ_atoms = sorted(templ_atoms, key=str)
        
        
    def _atom_mean(self, tatom):
        w_total = 0
        w_true = 0
        for bmrf in self.bmrfs:
            for gndatom in tatom.iterGroundings(bmrf):
                w = bmrf.bgnd_atoms[gndatom.idx].weight
                if gndatom.isTrue(bmrf.mrf.evidence): 
                    w_true += w
                w_total += w 
        return w_true / w_total
        
    def _compute_atom_means(self):
        '''
        Computes the _atom_means attribute storing all weighted 
        mean truth values of all template atoms.
        '''
        means = []
        for atom in self.templ_atoms:
            means.append(self._atom_mean(atom))
        self._atom_means = means
        
    
    class BoostedMRF(object):
        '''
        Extends the ordinary MRF by a list of BoostedGroundAtoms.
        '''
        
        def __init__(self, mrf):
            self.bgnd_atoms = [None] * len(mrf.gndAtoms)
            self.mrf = mrf
    
    class BoostedGroundAtom(object):
        '''
        An extension to ordinary ground atom with a weight and a probability
        assignment.
        '''
        
        def __init__(self, atom, idx, truth, prob, weight, mrf, cll):
            self.atom = atom
            self.idx = idx
            self.truth = truth
            self.weight = weight
            self.mrf = mrf
            self.cll = cll
            self.prob = prob
            self.set_cll(cll)
            
        def set_cll(self, cll):
            # compute the index of the value of the atomic block/partition
            # where this gnd atom is true to efficiently access the sufficient statistics 
            self.cll = cll
            partition = cll.atomIdx2partition[self.atom.idx] # get the partition that this gnd atom is part of
            self.partition_idx = partition.idx
            gndatomblock = partition.variables[0] # get the atomic block of this gnd atom
            value_tuple = [0] * len(gndatomblock.gndatoms) 
            value_tuple[gndatomblock.gndatoms.index(self.atom)] = 1
            value_tuple = tuple(value_tuple)
            self.value_idx = gndatomblock.getValueIndex(value_tuple) # get index of the value of the atomic block where this gnd atom is true
            
            
        def __repr__(self):
            return 'BoostedGroundAtom(%s, %.1f, %.3f, %.3f)' % (str(self.atom), self.truth, self.prob, self.weight)
        
        
    
    
        