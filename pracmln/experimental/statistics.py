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
from collections import defaultdict

import sys
from pprint import pprint

from pracmln.logic.common import Logic
from tabulate import tabulate
from pracmln.mln.grounding.default import EqualityConstraintGrounder
from pracmln.mln.util import dict_subset, out, ifNone, ProgressBar
import math
from pracmln.mln.base import MLN
from pracmln.mln.database import Database
from pracmln import praclog
from matplotlib import pyplot as plt
import numpy as np

from utils.clustering import CorrelationClustering


class AtomCorrelationMatrix(object):
    '''
    Matrix of correlations of atoms within a formula.
    '''

    def __init__(self, mrfs, formula, group_templ_atoms=False):
        '''
        group_templ_atoms:     do not compute the correlations of atoms
                               that have been generated from the same template.
        '''
        self.mln = formula.mln
        self.mrfs = mrfs
        self.formula = formula
        self.groups = {}  # maps an atom to its template
        if group_templ_atoms:
            atoms = []
            for literal in formula.literals():
                literal.idx = formula.idx
                for templ in literal.template_variants():
                    atoms.append(templ)
                    self.groups[templ] = literal
        else:
            atoms = formula.templ_atoms()
        self.atoms = sorted(atoms, key=str)
        self.atom2idx = dict([(a, i) for i, a in enumerate(self.atoms)])
        self.corr = defaultdict(dict)
        eq_constraints = formula.atomic_constituents(oftype=Logic.Equality)
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
        return self.corr[i][j] if i >= j else self.corr[j][i]

    def __str__(self):
        table = [[str(self.atoms[i])] + [self[i, j] for j in range(len(self.atoms))] for i in range(len(self.atoms))]
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

    def show(self, crange=None, block=True):
        if crange is None:
            crange = [-1, 1]
        fig = plt.figure()
        labels = map(str, self.atoms)
        ax = fig.add_subplot(111)
        vals = np.around([[ifNone(self[i, j], 0, lambda n: n if crange[1] > n > crange[0] else 0) for j in range(len(self.atoms))] for i in range(len(self.atoms))], 2)
        table = ax.matshow(vals, cmap=plt.cm.coolwarm, vmin=-.5, vmax=.5)
        ax.set_xticklabels(labels)
        ax.set_yticklabels(labels)
        ax.set_xticks(range(len(self.atoms)))
        for label in ax.get_xmajorticklabels():
            label.set_rotation(90)
        ax.set_yticks(range(len(self.atoms)))
        fig.colorbar(table)
        plt.show(block=block)

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
        conj = self.mln.logic.conjunction([atom1, atom2], mln=self.mln)
        ecg = EqualityConstraintGrounder(self.mln, EqualityConstraintGrounder.vardoms_from_formula(conj),
                                         'alltrue', *eq_constraints)
        valid_varassignments = list(ecg.iter_valid_variable_assignments())
        # first, compute the (weighted) sample means
        w1_total = w2_total = w2_true = w1_true = 0.
        datapoints = []  # stores tuples (truth1, truth2, w1, w2) for later covariance computation
        for mrf in self.mrfs:
            for varassign in conj.itervargroundings(mrf):
                if not any([dict_subset(valid, varassign) for valid in valid_varassignments]):
                    continue
                gconj = conj.ground(mrf, varassign)
                (gndlit1, gndlit2) = gconj.children
                w1 = gndlit1.gndatom.weight
                w2 = gndlit2.gndatom.weight
                w1_true += gndlit1(mrf.evidence) * w1
                w2_true += gndlit2(mrf.evidence) * w2
                w1_total += w1
                w2_total += w2
                datapoints.append((gndlit1(mrf.evidence), gndlit2(mrf.evidence), w1, w2))
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
        n = float(len(datapoints))
        var1 /= (n - 1) / n * w1_total
        var2 /= (n - 1) / n * w2_total
        var1 = max(1e-5, var1)
        var2 = max(1e-5, var2)
        return w_total / (w_total ** 2 - wsq_total) * cov / math.sqrt(var1 * var2)


if __name__ == '__main__':
    praclog.level(praclog.INFO)
    mln = MLN(mlnfile='/home/nyga/work/code/pracmln/models/object-detection-new.mln', logic='FirstOrderLogic',
              grammar='PRACGrammar')
    statmln = mln.copy()
    dbs = Database.load(mln, dbfiles='/home/nyga/work/code/pracmln/models/scenes-new.db', ignore_unknown_preds=True)
    mln_ = mln.materialize(*dbs)
    mrfs = []
    out('grounding...')
    bar = ProgressBar(width=150, steps=len(dbs), color='green')
    for i, db in enumerate(dbs):
        bar.update(bar.value, 'Grounding database %s' % (i+1))
        mrf = mln_.ground(db)
        mrf.apply_cw()
        for gndatom in mrf.gndatoms:
            gndatom.weight = 1
        mrfs.append(mrf)
        bar.inc()
        sys.stdout.flush()
    statmln.domains = mln_.domains
    out('computing correlations...')
    corr = AtomCorrelationMatrix(mrfs, statmln.formulas[0], group_templ_atoms=True)
    out('plotting...')
    corr.show(crange=[-1, 0], block=False)
    corr.show(crange=[0, 1], block=False)
    out('clustering...')
    cluster = CorrelationClustering(correlations=corr.iteritems(), corr_matrix=corr, thr=None)
    pprint(dict(cluster.cluster2data))
    pprint(dict(cluster.clusters))
