# -*- coding: utf-8 -*-
#
# Fast Existential Grounding
#
# (C) 2016 by Marc Niehaus
#
# Contains code from pracmln and uses the pracmln framework
#
# (C) 2012-2015 by Daniel Nyga
#     2006-2011 by Dominik Jain
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

import logging

from pracmln.logic.fol import Lit, Conjunction
from pracmln.mln.constants import auto
from pracmln.mln.grounding.default import DefaultGroundingFactory
from pracmln.mln.util import dict_union

logger = logging.getLogger(__name__)


class InSomeCasesFasterConjunctionGrounding(DefaultGroundingFactory):
    """
    This class provides a grounder which is sometimes faster than the normal fast conjunction grounder.
    It is applicable if the formulas consist of conjunctions of atoms. Negated atoms are not allowed!
    The grounder is especially useful if one variable is used in more than one ground atom.
    The current implementation supports first-order logic only.
    In a nutshell, it first collects all atoms that might be true given the evidence for each predicate
    Then, it grounds each formula:
    First of all, the atoms are sorted by the number of possible true ground atoms
    Then, the variables values for each atom are determined. The variable values tried in the end are
    those creatable from an intersection of the variable values of the atoms.

    An example is the formula foo(?x) ^ bar(?x).
    Assume the evidence is
    foo(A) True
    foo(B) True
    foo(C) True
    foo(D) False
    bar(A) ?
    bar(B) False
    bar(C) False
    bar(D) True
    The algorithm first looks at bar since there are less ground atoms which might be true (2).
    The possible values for variable ?x considering bar are A and D.
    The possible values for variable ?x considering foo are A, B and C.
    The intersection of these values is A.
    Thus, there is only one ground fromula: foo(A) ^ bar(A).
    """

    def __init__(self, mrf, simplify=False, unsatfailure=False, formulas=None, cache=auto, **params):
        DefaultGroundingFactory.__init__(self, mrf, simplify, unsatfailure, formulas, cache, **params)

    def _itergroundings(self, simplify=True, unsatfailure=True):
        predicate_to_true_ground_atoms = self.__get_predicate_to_true_ga_map()
        variable_domain_cache = {}
        for formula in self.formulas:
            if not self.__is_applicable(formula):
                logger.info("FasterConjunctionGrounding is not applicable for formula %s, using default grounding..." %
                            formula)
                for gf in formula.itergroundings(self.mrf):
                    yield gf
            else:
                for gf in self.__ground_formula(formula, predicate_to_true_ground_atoms, variable_domain_cache):
                    yield gf

    def __is_applicable(self, formula):
        if not isinstance(formula, Conjunction):
            return False
        return not [c for c in formula.children if not isinstance(c, Lit) or c.negated] #TODO: Allow negation...

    def __get_predicate_to_true_ga_map(self):
        to_return = {}
        for gnd_atom in self.mrf.gndatoms:
            if self.mrf.evidence[gnd_atom.idx] == 0:
                continue
            predicate = gnd_atom.predname
            if not predicate in to_return:
                to_return[predicate] = []
            to_return[predicate].append(gnd_atom)
        return to_return

    def __ground_formula(self, formula, predicate_to_true_ground_atoms, cache):
        if not all([l.predname in predicate_to_true_ground_atoms for l in formula.children]):
            return
        literals = [l for l in formula.children if len([a for a in l.args if self.mrf.mln.logic.isvar(a)])>0]
        literals = sorted(literals, key=lambda l: len(predicate_to_true_ground_atoms[l.predname]))
        allowed_variable_domains = {}
        for literal in literals:
            literal_var_doms = self.__get_literal_variable_domains(literal, predicate_to_true_ground_atoms, cache)
            for variable, values in list(literal_var_doms.items()):
                if variable not in allowed_variable_domains:
                    allowed_variable_domains[variable] = set(values)
                else:
                    allowed_variable_domains[variable].intersection_update(values)
            if not all(allowed_variable_domains.values()):
                return
        variables = list(allowed_variable_domains.keys())
        for assignment in self.__get_variable_assignments(formula, allowed_variable_domains, variables, {}):
            ground_formula = formula.ground(self.mrf, assignment)
            yield ground_formula

    def __get_literal_variable_domains(self, literal, predicate_to_true_ground_atoms, variable_domain_cache):
        logic = self.mrf.mln.logic
        cache_key = tuple([literal.predname] + [ia for ia in enumerate(literal.args) if not logic.isvar(ia[1])])
        if cache_key in variable_domain_cache:
            literal_var_idx_domains = variable_domain_cache[cache_key]
        else:
            variable_indices = [idx for idx, arg in enumerate(literal.args) if logic.isvar(arg)]
            non_variable_literal_args = [arg for arg in literal.args if not logic.isvar(arg)]
            literal_var_idx_domains = {idx: set() for idx in variable_indices}
            for ground_atom in predicate_to_true_ground_atoms[literal.predname]:
                non_variable_args = [a for i, a in enumerate(ground_atom.args) if not logic.isvar(literal.args[i])]
                if non_variable_args != non_variable_literal_args:
                    continue
                variable_args = [arg for idx, arg in enumerate(ground_atom.args) if logic.isvar(literal.args[idx])]
                for index, value in zip(variable_indices, variable_args):
                    literal_var_idx_domains[index].add(value)
            variable_domain_cache[cache_key] = literal_var_idx_domains
        return {literal.args[idx]: domain for idx, domain in list(literal_var_idx_domains.items())}

    def __get_variable_assignments(self, formula, variable_domains, remaining_variables, assignment):
        if not remaining_variables:
            yield assignment
        else:
            for variable_value in variable_domains[remaining_variables[0]]:
                new_ass = dict_union(assignment, {remaining_variables[0]: variable_value})
                for ass in self.__get_variable_assignments(formula, variable_domains, remaining_variables[1:], new_ass):
                    yield ass
