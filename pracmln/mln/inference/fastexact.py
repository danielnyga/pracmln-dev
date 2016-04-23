# -*- coding: utf-8 -*-
#
# Fast Exact Inference
#
# (C) 2015 by Marc Niehaus
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

from pracmln.logic.fuzzy import FuzzyLogic
from pracmln.mln.grounding.fastexistential import FastExistentialGrounding
from pracmln.mln.inference.infer import Inference
from pracmln.mln.constants import HARD
from pracmln.logic.common import Conjunction, GroundLit, TrueFalse, Disjunction, Equality
from operator import mul
import numpy
from networkx import Graph, find_cliques_recursive
from itertools import combinations

#TODO: add networkx to license file?!

from pracmln.mln.mrfvars import FuzzyVariable

logger = logging.getLogger(__name__)


class FastExact(Inference):
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)

    def _run(self):
        queries = [FastExact.QueryFormula(self.mrf, query, index) for index, query in enumerate(self.queries)]
        ground_formulas, evidence = self.__get_ground_formulas()
        logger.info("Grounding finished!")
        world_count = self.__get_world_count_for_evidence_and_queries(evidence, *queries)
        queries_with_probability_zero = filter(lambda q: world_count[q] == 0, queries)
        to_return = {q.query_formula: 0.0 for q in queries_with_probability_zero}
        other_queries = filter(lambda q: world_count[q] > 0, queries)
        if not other_queries:
            return to_return
        formula_combinations = self.__combine_formulas(ground_formulas)
        query_combinations = self.__assign_queries_and_formula_combinations(other_queries, formula_combinations)
        self.__assign_world_number(formula_combinations, query_combinations)
        to_return.update(self.__calculate_probability(evidence, other_queries, formula_combinations, world_count))
        return to_return

    def __get_ground_formulas(self):
        formulas = list(self.mrf.formulas)
        grounder = FastExistentialGrounding(self.mrf, False, False, formulas, -1)
        ground_formulas = list(grounder.itergroundings())
        hard_ground_formulas = filter(lambda f: f.weight == HARD, ground_formulas)
        logical_evidence = [self.mln.logic.gnd_lit(self.mrf.gndatom(i), self.mrf.evidence[i] == 0, self.mrf.mln)
                            for i in range(0, len(self.mrf.evidence)) if self.mrf.evidence[i] is not None]
        if logical_evidence:
            hard_ground_formulas.append(self.mln.logic.conjunction(logical_evidence, self.mrf.mln)
                                        if len(logical_evidence) > 1 else logical_evidence[0])
        # TODO: Make sure that a conjunction in the evidence does not exist twice...
        hard_ground_formulas_as_dnf = self.__create_dnf(hard_ground_formulas)
        non_hard_ground_formulas = filter(lambda f: f.weight != HARD, ground_formulas)
        non_hard_ground_formulas = [self.__remove_equality(formula) for formula in non_hard_ground_formulas]
        non_hard_ground_formulas = filter(lambda f: f is not None, non_hard_ground_formulas)
        ground_formulas = [FastExact.GroundFormula(self.mrf,g,g.idx,i) for i, g in enumerate(non_hard_ground_formulas)]
        to_return = [(hard_ground_formulas_as_dnf*gf).children for gf in ground_formulas]
        return reduce(lambda l1, l2: l1+l2, to_return, tuple()), hard_ground_formulas_as_dnf

    def __create_dnf(self, formulas):
        #TODO: Improve implementation - First converting to cnf and then to dnf is probably not efficient (but easy^^)
        if not formulas:
            return FastExact.DisjunctiveNormalForm(self.mrf)
        if len(formulas) == 1 and isinstance(formulas[0], GroundLit):
            return FastExact.DisjunctiveNormalForm(self.mrf, FastExact.GroundLiteralConjunction(self.mrf, formulas[0]))
        if len(formulas) == 1:
            formulas = formulas[0]
        else:
            formulas = self.mln.logic.conjunction(formulas, self.mln)
        if not FastExact.__is_dnf(formulas):
            logger.warn("Formula is not in dnf, converting formula to cnf and cnf to dnf (Might cause space explosion)")
            if not FastExact.__is_cnf(formulas):
                formulas = formulas.cnf()
            formulas = self.__convert_cnf_to_dnf(formulas)
        disjunction_children = formulas.children if isinstance(formulas, Disjunction) else [formulas]
        disjunction_children = [self.__remove_equality(child) for child in disjunction_children]
        disjunction_children = filter(lambda c: c is not None, disjunction_children)
        disjunction_children = [FastExact.GroundLiteralConjunction(self.mrf, child) for child in disjunction_children]
        disjunction_children = filter(lambda c: c.consistent(), disjunction_children)
        if not disjunction_children:
            raise Exception("There is no world satisfying the evidence!")
        return FastExact.DisjunctiveNormalForm(self.mrf, *disjunction_children)

    def __convert_cnf_to_dnf(self, formula):
        def enumerate_conjunctions_recursively(remaining_disjunctions, previous_conjunction):
            if not remaining_disjunctions:
                return [previous_conjunction]
            current = remaining_disjunctions[0]
            rest = remaining_disjunctions[1:]
            if isinstance(current, GroundLit):
                current = [current]
            elif isinstance(current, Disjunction):
                current = current.children
            else:
                raise Exception("Formula %s is not a CNF!", str(formula))
            to_return = []
            for ground_literal in current:
                to_return += enumerate_conjunctions_recursively(rest, previous_conjunction + [ground_literal])
            return to_return

        if isinstance(formula, GroundLit) or isinstance(formula, Disjunction):
            return formula
        elif isinstance(formula, Conjunction):
            dnf_as_list = enumerate_conjunctions_recursively(list(formula.children), [])
            return self.mln.logic.disjunction([Conjunction(c, self.mln) for c in dnf_as_list], self.mln)
        else:
            raise Exception("Formula %s is not a CNF!" % str(formula))

    @staticmethod
    def __is_conjunction_or_gnd_literal(formula):
        if isinstance(formula, Conjunction):
            return all([isinstance(f, GroundLit) for f in formula.children])
        elif isinstance(formula, GroundLit) or (isinstance(formula, TrueFalse) and formula.truth()==1):
            return True
        else:
            return False

    @staticmethod
    def __is_cnf_or_dnf(formula, first_level_literal, second_level_literal):
        if isinstance(formula, first_level_literal):
            conjunction = formula.children
        elif isinstance(formula, GroundLit):
            return True
        elif isinstance(formula, second_level_literal):
            conjunction = [formula]
        else:
            return False
        for disjunction in conjunction:
            if isinstance(disjunction, second_level_literal):
                if not all([isinstance(g, GroundLit) or (isinstance(g, TrueFalse) and g.truth()==1)
                            for g in disjunction.children]):
                    break
            elif not isinstance(disjunction, GroundLit):
                break
        else:
            return True
        return False

    @staticmethod
    def __is_cnf(formula):
        return FastExact.__is_cnf_or_dnf(formula, Conjunction, Disjunction)

    @staticmethod
    def __is_dnf(formula):
        return FastExact.__is_cnf_or_dnf(formula, Disjunction, Conjunction)

    def __remove_equality(self, formula):
        conjunction = formula.children if isinstance(formula, Conjunction) else [formula]
        if filter(lambda c: isinstance(c, Equality) and c.truth() == 0, conjunction):
            return None
        gnd_literals = filter(lambda g: not isinstance(g, Equality), conjunction)
        if not gnd_literals:
            return self.mln.logic.true_false(1, self.mln, formula.idx)
        to_return = gnd_literals[0] if len(gnd_literals) == 1 else self.mln.logic.conjunction(gnd_literals, self.mln)
        to_return.idx = formula.idx
        return to_return

    def __combine_formulas(self, formulas):
        combination_to_identity = {}

        def add_to_combination_to_identity(formula_combination):
            if formula_combination in combination_to_identity:
                other = combination_to_identity[formula_combination]
                other.union_formulas(formula_combination)
                return other
            combination_to_identity[formula_combination] = formula_combination
            return formula_combination

        formulas = [add_to_combination_to_identity(f) for f in formulas]
        all_combinations = {tuple([i]): f for i, f in enumerate(formulas)}
        formula_graph = Graph()
        formula_graph.add_nodes_from(range(0, len(formulas)))
        for i1, f1 in enumerate(formulas[:-1]):
            for i2, f2 in enumerate(formulas[i1+1:], start=i1+1):
                combination = f1 * f2
                if not combination.consistent():
                    continue
                t = tuple(sorted((i1, i2)))
                all_combinations[t] = add_to_combination_to_identity(combination)
                formula_graph.add_edge(i1, i2)
        combination_indices = []
        cliques = list(find_cliques_recursive(formula_graph))
        for maximal_clique in cliques:
            for combination_size in range(3, len(maximal_clique)+1):
                clique_combinations = [tuple(sorted(c)) for c in combinations(maximal_clique, combination_size)]
                if len(combination_indices) >= combination_size-2:
                    combination_indices[combination_size-3].update(set(clique_combinations))
                else:
                    combination_indices.append(set(clique_combinations))
        for iteration in combination_indices:
            for combination in iteration:
                fc = all_combinations[combination[:-1]] * formulas[combination[-1]]
                fc = add_to_combination_to_identity(fc)
                all_combinations[combination] = fc
        return combination_to_identity.keys()

    def __assign_queries_and_formula_combinations(self, queries, evidence_combinations):
        query_combinations = {}
        for query in queries:
            query_combinations[query] = []
            combinations = [ec * query for ec in evidence_combinations]
            combination_dict = {}
            for combination in combinations:
                if not combination.consistent():
                    continue
                if combination not in combination_dict:
                    combination_dict[combination] = []
                combination_dict[combination].append(combination)
            for _, equivalent_combinations in combination_dict.items():
                equivalent_combinations.sort(key= lambda c: len(c.evidence_combination.ground_formulas))
                most_specific_combination = equivalent_combinations[-1]
                most_specific_combination.evidence_combination.add_query_combination(most_specific_combination)
                query_combinations[query].append(most_specific_combination)
        return query_combinations

    def __assign_world_number(self, evidence_combinations, query_combinations):
        for formula in evidence_combinations:
            worlds = self.__get_world_count_for_conjunction(formula, *formula.query_combinations)
            formula.maximum_number_of_worlds = worlds[formula]
            for query_combination in formula.query_combinations:
                query_combination.maximum_number_of_worlds = worlds[query_combination]

        for combined_formulas in [c for _, c in query_combinations.items()] + [evidence_combinations]:
            container_of = {}
            contained_in = set()
            for contained in combined_formulas:
                for container in combined_formulas:
                    if contained < container:
                        contained_in.add(container)
                        if contained not in container_of:
                            container_of[contained] = []
                        container_of[contained].append(container)
            no_containments = filter(lambda formula: formula not in contained_in, combined_formulas)

            def set_number_of_worlds_recursively(formula):
                if formula.actual_number_of_worlds is not None:
                    return formula.actual_number_of_worlds
                child_value_list = container_of[formula] if formula in container_of else []
                child_values = sum([set_number_of_worlds_recursively(child_value) for child_value in child_value_list])
                formula.actual_number_of_worlds = formula.maximum_number_of_worlds - child_values
                return formula.actual_number_of_worlds

            for f in no_containments:
                set_number_of_worlds_recursively(f)

    def __get_world_count_for_conjunction(self, base_conjunction, *extending_conjunctions):
        base_world = {index: truth for index, _, truth in base_conjunction.ground_atom_indices_and_truth_values}
        base_world_count = reduce(mul, [variable.valuecount(base_world) for variable in self.mrf.variables], 1)
        to_return = {base_conjunction: base_world_count}
        for extension in extending_conjunctions:
            additional_world = {index: truth for index, _, truth in extension.ground_atom_indices_and_truth_values -
                                base_conjunction.ground_atom_indices_and_truth_values}
            additional_variable_indices = {self.mrf.variable(self.mrf.gndatom(gnd_atom_idx)).idx
                                           for gnd_atom_idx in additional_world.keys()}
            combined_world = dict(base_world, **additional_world)
            extension_world_count = base_world_count
            for variable_index in additional_variable_indices:
                variable = self.mrf.variable(variable_index)
                extension_world_count *= variable.valuecount(combined_world)
                extension_world_count /= variable.valuecount(base_world)
            to_return[extension] = extension_world_count
        return to_return

    def __get_world_count_for_evidence_and_queries(self, evidence_dnf, *query_conjunctions):
        worlds = {conjunction: 0 for conjunction in query_conjunctions}
        worlds[evidence_dnf] = 0
        children = evidence_dnf.children
        if not children:
            children = [FastExact.GroundLiteralConjunction(self.mrf, self.mln.logic.true_false(1, self.mln))]
        for conjunction in children:
            consistent_queries = filter(lambda q: conjunction.get_combined_ground_atom_indices_and_truth_values(q),
                                        query_conjunctions)
            conjunction_worlds = self.__get_world_count_for_conjunction(conjunction, *consistent_queries)
            for formula, world_count in conjunction_worlds.items():
                if formula in worlds:
                    worlds[formula] += world_count
                if formula == conjunction:
                    worlds[evidence_dnf] += world_count
        return worlds

    def __calculate_probability(self, evidence, queries, evidence_combinations, world_count):
        def get_number_of_worlds_and_sum(formula_combination):
            def exp(number):
                result = numpy.exp(number)
                return long(result) if result > 1000000 else result

            def product(sequence):
                return reduce(lambda x, y: x*y, sequence, 1)

            if isinstance(self.mln.logic, FuzzyLogic):
                def get_conjunction_truth(ground_formula):
                    to_return = min([1 - truth if negated else truth for _, negated, truth in
                                ground_formula.ground_atom_indices_and_truth_values])
                    return to_return

                exp_sum = product([exp(f.weight*get_conjunction_truth(f)) for f in formula_combination.ground_formulas])
            else:
                exp_sum = product([exp(f.weight) for f in formula_combination.ground_formulas])
            to_return = [(q.query, q.actual_number_of_worlds, q.actual_number_of_worlds * exp_sum)
                         for q in formula_combination.query_combinations]
            to_return.append((None, formula_combination.actual_number_of_worlds,
                              formula_combination.actual_number_of_worlds * exp_sum))
            return to_return

        def divide(fraction_nominator, fraction_denominator):
            if denominator == 0:
                raise Exception("There are no worlds modeling the evidence!")
            else:
                precision = long(1000000)
                return ((precision * fraction_nominator)/fraction_denominator)/float(precision)

        exp_sums = {query: 0 for query in queries+[None]}
        number_of_worlds = {query: 0 for query in queries+[None]}
        for evidence_combination in evidence_combinations:
            for query, world_number, world_sum in get_number_of_worlds_and_sum(evidence_combination):
                exp_sums[query] += world_sum
                number_of_worlds[query] += world_number
        denominator = world_count[evidence] - number_of_worlds[None] + exp_sums[None]
        return {query.query_formula: divide(world_count[query] - number_of_worlds[query] + exp_sums[query], denominator)
                for query in queries}

    class GroundLiteralConjunction(object):
        def __init__(self, mrf, formula_or_other_ground_literal_conjunction=None):
            self._mrf = mrf
            if formula_or_other_ground_literal_conjunction is None:
                return
            if hasattr(formula_or_other_ground_literal_conjunction, "ground_atom_indices_and_truth_values"):
                self._ground_atom_indices_and_truth_values = \
                    set(formula_or_other_ground_literal_conjunction.ground_atom_indices_and_truth_values)
            else:
                self._ground_atom_indices_and_truth_values = set()
                if isinstance(formula_or_other_ground_literal_conjunction, Conjunction):
                    ground_literals = formula_or_other_ground_literal_conjunction.children
                elif isinstance(formula_or_other_ground_literal_conjunction, GroundLit):
                    ground_literals = [formula_or_other_ground_literal_conjunction]
                elif isinstance(formula_or_other_ground_literal_conjunction, TrueFalse) and \
                        formula_or_other_ground_literal_conjunction.truth() == 1.0:
                    ground_literals = []
                else:
                    raise Exception("Formulas must be conjunctions of ground literals - %s is none" %
                                    formula_or_other_ground_literal_conjunction)
                for ground_literal in ground_literals:
                    if isinstance(self._mrf.mln.logic, FuzzyLogic) and hasattr(ground_literal, "gndatom") and \
                            isinstance(self._mrf.variable(ground_literal.gndatom), FuzzyVariable):
                        index = ground_literal.gndatom.idx
                        truth = self._mrf.evidence[index]
                    elif isinstance(ground_literal, GroundLit):
                        index = ground_literal.gndatom.idx
                        truth = 0 if ground_literal.negated else 1
                    elif isinstance(ground_literal, TrueFalse) and ground_literal.truth == 1:
                        continue
                    else:
                        raise Exception("Formulas must be conjunctions of ground literals - %s is none" %
                                    formula_or_other_ground_literal_conjunction)
                    self._ground_atom_indices_and_truth_values.add((index, ground_literal.negated, truth))
            self._update_hash_code()

        def __hash__(self):
            return self.__hash_code

        def __eq__(self, other):
            return self._ground_atom_indices_and_truth_values == other.ground_atom_indices_and_truth_values

        def __ne__(self, other):
            return not self.__eq__(other)

        def __lt__(self, other):
            return self.ground_atom_indices_and_truth_values < other.ground_atom_indices_and_truth_values

        def __mul__(self, other):
            indices_and_truth_values = self.get_combined_ground_atom_indices_and_truth_values(other, False)
            if isinstance(other, FastExact.GroundFormula) or isinstance(other, FastExact.EvidenceFormulaCombination):
                return FastExact.EvidenceFormulaCombination(self._mrf, indices_and_truth_values, self, other)
            elif isinstance(other, FastExact.QueryFormula):
                return FastExact.QueryFormulaCombination(self._mrf, indices_and_truth_values, self, other)
            else:
                return FastExact.FormulaCombination(self._mrf, indices_and_truth_values)

        def __str__(self):
            def get_ground_atom_string(index, negated, truth):
                prefix = "!" if negated else ""
                infix = str(self._mrf.gndatom(index))
                suffix = "=%f" % truth if 0 < truth < 1 or negated and truth == 1 or not negated and truth == 0 else ""
                return prefix + infix + suffix

            ground_atoms = [get_ground_atom_string(i, n, t) for i, n, t in self._ground_atom_indices_and_truth_values]
            return reduce(lambda ga1, ga2: ga1 + " ^ " + ga2, ground_atoms)

        def __repr__(self):
            return self.__str__()

        @property
        def ground_atom_indices_and_truth_values(self):
            return self._ground_atom_indices_and_truth_values

        def get_combined_ground_atom_indices_and_truth_values(self, other, check_consistency=True):
            to_return = set(self.ground_atom_indices_and_truth_values)
            to_return.update(other.ground_atom_indices_and_truth_values)
            if not check_consistency:
                return to_return
            return to_return if self.consistent(to_return) else None

        def consistent(self, ground_atom_indices_and_truth_values=None):
            if ground_atom_indices_and_truth_values is None:
                ground_atom_indices_and_truth_values = self._ground_atom_indices_and_truth_values
            assignment = {}
            for ground_atom_index, negated, truth_value in ground_atom_indices_and_truth_values:
                if negated and truth_value == 1.0 or not negated and truth_value == 0.0:
                    return False
                values_to_set = []
                if truth_value == 1:
                    variable = self._mrf.variable(self._mrf.gndatom(ground_atom_index))
                    for gnd_atom in variable.gndatoms:
                        values_to_set.append((gnd_atom.idx, 1 if gnd_atom.idx == ground_atom_index else 0))
                else:
                    values_to_set.append((ground_atom_index, truth_value))
                for index, value in values_to_set:
                    current_value = assignment[index] if index in assignment else None
                    if current_value is not None and current_value != value:
                        return False
                    assignment[index] = value
            return True

        def _update_hash_code(self):
            self.__hash_code = sum([idx*97+truth for idx, negated, truth in self._ground_atom_indices_and_truth_values])

    class GroundFormula(GroundLiteralConjunction):
        def __init__(self, mrf, formula_or_other_combination, formula_index, ground_formula_index):
            self.__formula_index = formula_index
            self.__ground_formula_index = ground_formula_index
            FastExact.GroundLiteralConjunction.__init__(self, mrf, formula_or_other_combination)

        @property
        def formula_index(self):
            return self.__formula_index

        @property
        def ground_formula_index(self):
            return self.__ground_formula_index

        @property
        def weight(self):
            return self._mrf.mln.weight(self.formula_index)

        def __hash__(self):
            return self.__ground_formula_index

        def __eq__(self, other):
            return self.ground_formula_index == other.ground_formula_index

    class QueryFormula(GroundLiteralConjunction):
        def __init__(self, mrf, formula, query_index):
            self.__query_index = query_index
            FastExact.GroundLiteralConjunction.__init__(self, mrf, formula)
            self.__query_formula = formula

        @property
        def query_index(self):
            return self.__query_index

        @property
        def query_formula(self):
            return self.__query_formula

    class FormulaCombination(GroundLiteralConjunction):
        def __init__(self, mrf, ground_atom_indices_and_truth_values):
            self.__maximum_number_of_worlds = None
            self.__actual_number_of_worlds = None
            FastExact.GroundLiteralConjunction.__init__(self, mrf, None)
            self._ground_atom_indices_and_truth_values = ground_atom_indices_and_truth_values
            self._update_hash_code()

        @property
        def maximum_number_of_worlds(self):
            return self.__maximum_number_of_worlds

        @maximum_number_of_worlds.setter
        def maximum_number_of_worlds(self, value):
            self.__maximum_number_of_worlds = value

        @property
        def actual_number_of_worlds(self):
            return self.__actual_number_of_worlds

        @actual_number_of_worlds.setter
        def actual_number_of_worlds(self, value):
            self.__actual_number_of_worlds = value

    class EvidenceFormulaCombination(FormulaCombination):
        def __init__(self, mrf, ground_atom_indices_and_truth_values, *combined_formulas):
            self.__ground_formulas = set()
            for formula in combined_formulas:
                self.__ground_formulas.update({formula} if hasattr(formula, "formula_index") and
                                                           hasattr(formula, "ground_formula_index") else
                                              formula.ground_formulas if hasattr(formula, "ground_formulas") else set())
            self.__query_combinations = []
            FastExact.FormulaCombination.__init__(self, mrf, ground_atom_indices_and_truth_values)

        @property
        def ground_formulas(self):
            return self.__ground_formulas

        @property
        def query_combinations(self):
            return self.__query_combinations

        def add_query_combination(self, query_combination):
            self.__query_combinations.append(query_combination)

        def union_formulas(self, other_formula_combination):
            self.__ground_formulas.update(other_formula_combination.__ground_formulas)

    class QueryFormulaCombination(FormulaCombination):
        def __init__(self, mrf, ground_atom_indices_and_truth_values, evidence_combination, query):
            self.__evidence_combination = evidence_combination
            self.__query = query
            FastExact.FormulaCombination.__init__(self, mrf, ground_atom_indices_and_truth_values)

        @property
        def query(self):
            return self.__query

        @property
        def evidence_combination(self):
            return self.__evidence_combination

    class DisjunctiveNormalForm(object):
        def __init__(self, mrf, *children):
            self.__mrf = mrf
            self.__children = children
            self.__common_indices_and_truth_values = None

        def __mul__(self, other):
            if len(self.children) > 1:
                if self.__common_indices_and_truth_values is None:
                    self.__common_indices_and_truth_values = set.intersection(
                        *[c.ground_atom_indices_and_truth_values for c in self.children])
                other_atom_indices_and_truth_values = other.ground_atom_indices_and_truth_values
                if not other.consistent(self.__common_indices_and_truth_values | other_atom_indices_and_truth_values):
                    return FastExact.DisjunctiveNormalForm(self.__mrf)
            children = [child * other for child in self.__children]
            if not children:
                children = [FastExact.GroundLiteralConjunction(
                    self.__mrf, self.__mrf.mln.logic.true_false(1, self.__mrf.mln)) * other]
            return FastExact.DisjunctiveNormalForm(self.__mrf, *filter(lambda c: c.consistent(), children))

        def __str__(self):
            conjunctions = ["(" + str(conjunction) + ")" for conjunction in self.__children]
            if not conjunctions:
                return "True"
            return reduce(lambda c1, c2: c1 + " v " + c2, conjunctions)

        def __repr__(self):
            return self.__str__()

        @property
        def children(self):
            return self.__children
