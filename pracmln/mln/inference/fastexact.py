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
from copy import deepcopy

from pracmln.mln.errors import MRFValueException
from pracmln.mln.grounding.fastexistential import FastExistentialGrounding
from pracmln.mln.inference.infer import Inference
from pracmln.mln.constants import HARD
from pracmln.logic.fol import Conjunction, GroundLit, TrueFalse, Disjunction, Formula
from numpy import exp
from operator import mul

logger = logging.getLogger(__name__)


class FastExact(Inference):
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)

    def _run(self):
        to_return = {}
        ground_formulas, evidence = self.__get_ground_formulas()
        logger.info("Grounding finished!")
        formula_combinations = self.__combine_formulas(ground_formulas)
        self.__assign_world_number(formula_combinations)
        for query in self.queries:
            # TODO: Reuse evidence formula combinations...
            if not FastExact.__is_conjunction_or_gnd_literal(query):
                # TODO: Allow formulas in dnf...
                raise Exception("Queries must be conjunctions or ground literals!")
            query_ground_formulas = [self.__combine_dnf_and_conjunctions_to_dnf(query, gf) for gf in ground_formulas]
            query_ground_formulas = filter(lambda x: x is not None, query_ground_formulas)
            query_formula_combinations = self.__combine_formulas(query_ground_formulas)
            self.__assign_world_number(query_formula_combinations)
            p = self.__calculate_probability(query, query_formula_combinations, evidence, formula_combinations)
            to_return[query] = p
        return to_return

    def __get_world_as_formula(self, world):
        logical_evidence = []
        for i in range(0, len(world)):
            if world[i] is not None:
                if world[i] != 1 and world[i] != 0:
                    raise Exception("Unknown Probability value: " + str(world[i]))
                logical_evidence.append(GroundLit(self.mrf.gndatom(i), world[i] == 0, self.mrf.mln))
        return None if not logical_evidence else Conjunction(logical_evidence, self.mrf.mln)

    def __get_ground_formulas(self):
        formulas = list(self.mrf.formulas)
        evidence = self.__get_world_as_formula(self.mrf.evidence)
        if evidence:
            evidence.weight = HARD
            formulas.append(evidence)
        grounder = FastExistentialGrounding(self.mrf, False, False, formulas, -1)
        ground_formulas = list(grounder.itergroundings())
        # TODO: Make sure that a conjunction in the evidence does not exist twice...
        non_hard_ground_formulas = filter(lambda f: f.weight != HARD, ground_formulas)
        hard_ground_formulas_as_dnf = self.__combine_to_dnf(filter(lambda f: f.weight == HARD, ground_formulas))
        formulas_compatible_with_evidence = self.__combine_dnf_and_conjunctions_to_dnf(
            hard_ground_formulas_as_dnf, *non_hard_ground_formulas)
        if formulas_compatible_with_evidence is None:
            formulas_compatible_with_evidence = []
        elif not isinstance(formulas_compatible_with_evidence, Disjunction):
            formulas_compatible_with_evidence = [formulas_compatible_with_evidence]
        else:
            formulas_compatible_with_evidence = formulas_compatible_with_evidence.children
        return formulas_compatible_with_evidence, hard_ground_formulas_as_dnf

    def __combine_dnf_and_conjunctions_to_dnf(self, dnf, *conjunctions):
        if dnf is not None and not FastExact.__is_dnf(dnf):
            raise Exception("Formula %s is not in dnf and neither a Conjunction nor a Ground Literal!" % dnf)
        formulas_compatible_with_evidence = []
        for formula in conjunctions:
            variable_assignment, consistent = self.__check_consistency_and_get_world(formula)
            if not consistent:
                continue
            if dnf is None:
                formulas_compatible_with_evidence.append(formula)
                continue
            elif isinstance(dnf, Disjunction):
                disjunction = dnf.children
            elif isinstance(dnf, Conjunction) or \
                    isinstance(dnf, GroundLit):
                disjunction = [dnf]
            for sub_formula in disjunction:
                #TODO: Avoid squared complexity...
                _, consistent = self.__check_consistency_and_get_world(sub_formula, variable_assignment)
                if not consistent:
                    continue
                if isinstance(sub_formula, Conjunction) and isinstance(formula, Conjunction):
                    ground_literals = sub_formula.children + formula.children
                elif isinstance(sub_formula, GroundLit) and isinstance(formula, Conjunction):
                    ground_literals = [sub_formula] + formula.children
                elif isinstance(sub_formula, Conjunction) and isinstance(formula, GroundLit):
                    ground_literals = sub_formula.children + [formula]
                elif isinstance(sub_formula, GroundLit) and isinstance(formula, GroundLit):
                    ground_literals = [sub_formula, formula]
                else:
                    raise Exception("One of the following ground formulas is not a conjunction: %s or %s" %
                                    (formula, sub_formula))
                already_contained = set()
                set_of_ground_literals = []
                for ground_literal in ground_literals:
                    identifier = (ground_literal.gndatom.idx, ground_literal.negated)
                    if identifier in already_contained:
                        continue
                    already_contained.add(identifier)
                    set_of_ground_literals.append(ground_literal)
                if len(set_of_ground_literals) == 1:
                    set_of_ground_literals[0].idx = formula.idx
                    formulas_compatible_with_evidence.append(set_of_ground_literals[0])
                    continue
                formulas_compatible_with_evidence.append(Conjunction(set_of_ground_literals, self.mrf.mln, formula.idx))
        if len(formulas_compatible_with_evidence) == 0:
            return None
        elif len(formulas_compatible_with_evidence) == 1:
            return formulas_compatible_with_evidence[0]
        else:
            return Disjunction(formulas_compatible_with_evidence, self.mln)

    def __get_dnf_as_dict_of_truth_values(self, dnf):
        if isinstance(dnf, Disjunction):
            disjunction = dnf.children
        else:
            disjunction = [dnf]
        to_return = []
        for logical_world_restrictions in disjunction:
            evidence_truth_values = [None]*len(self.mrf.gndatoms)
            ground_literals = []
            if isinstance(logical_world_restrictions, GroundLit):
                ground_literals = [logical_world_restrictions]
            elif isinstance(logical_world_restrictions, Conjunction):
                ground_literals = logical_world_restrictions.children
            elif not (isinstance(logical_world_restrictions, TrueFalse) and logical_world_restrictions.value == 1):
                raise Exception("Unknown formula type:" + str(type(logical_world_restrictions)))
            for ground_literal in ground_literals:
                values_to_set = []
                new_value = 0 if ground_literal.negated else 1
                if new_value == 1:
                    variable = self.mrf.variable(ground_literal.gndatom)
                    for gnd_atom in variable.gndatoms:
                        values_to_set.append((gnd_atom.idx, 1 if gnd_atom.idx == ground_literal.gndatom.idx else 0))
                else:
                    values_to_set.append((ground_literal.gndatom.idx, 0))
                for index, value in values_to_set:
                    current_value = evidence_truth_values[index]
                    if current_value is not None and current_value != value:
                        return None
                    evidence_truth_values[index] = value
            for variable in self.mrf.variables:
                try:
                    variable.consistent(evidence_truth_values)
                except MRFValueException as e:
                    break
            else:
                to_return.append(dict(enumerate(evidence_truth_values)))
        return to_return

    def __get_world_count(self, logical_world_restrictions):
        if logical_world_restrictions is None:
            return 0
        evidences = self.__get_dnf_as_dict_of_truth_values(logical_world_restrictions)
        if not evidences:
            return 0

        return sum([reduce(mul, [variable.valuecount(f) for variable in self.mrf.variables], 1) for f in evidences])

    def __calculate_probability(self, query, query_formulas, evidence, evidence_formulas):
        def get_world_probability(formula_combinations):
            def product(sequence):
                return reduce(lambda x, y: x*y, sequence, 1)

            def get_exp_sum_for_combination(combination):
                return combination.actual_number_of_worlds*product([long(exp(f.weight)) for f in combination.formulas])

            number_of_worlds = sum(combination.actual_number_of_worlds for combination in formula_combinations)
            exp_sum = sum(get_exp_sum_for_combination(combination) for combination in formula_combinations)
            return number_of_worlds, exp_sum

        def divide(nominator, denominator):
            if denominator == 0:
                raise Exception("There are no worlds modeling the evidence!")
            else:
                precision = long(1000000)
                return ((precision * nominator)/denominator)/float(precision)

        evidence_world_number, evidence_world_sum = get_world_probability(evidence_formulas)
        query_world_number, query_world_sum = get_world_probability(query_formulas)
        return divide((
                    self.__get_world_count(self.__combine_dnf_and_conjunctions_to_dnf(evidence, query)) -
                    query_world_number +
                    query_world_sum
               ),
               (
                    self.__get_world_count(evidence) -
                    evidence_world_number +
                    evidence_world_sum
               ))

    def __check_consistency_and_get_world(self, formula, partial_assignment=None):
        #TODO: Use variables instead of ground atoms here...
        formula_is_conjunction = isinstance(formula, Conjunction)
        if formula_is_conjunction:
            for child in formula.children:
                formula_is_conjunction = formula_is_conjunction and isinstance(child, GroundLit)
        if not formula_is_conjunction and not isinstance(formula, GroundLit):
            raise Exception("The formula %s is not a conjunction (Only conjunctions are supported!)" % str(formula))
        assignment = deepcopy(partial_assignment) if partial_assignment is not None else [None]*len(self.mrf.gndatoms)
        for ground_literal in [formula] if isinstance(formula, GroundLit) else formula.children:
            values_to_set = []
            new_value = 0 if ground_literal.negated else 1
            if new_value == 1:
                variable = self.mrf.variable(ground_literal.gndatom)
                for gnd_atom in variable.gndatoms:
                    values_to_set.append((gnd_atom.idx, 1 if gnd_atom.idx == ground_literal.gndatom.idx else 0))
            else:
                values_to_set.append((ground_literal.gndatom.idx, 0))
            for index, value in values_to_set:
                current_value = assignment[index]
                if current_value is not None and current_value != value:
                    return assignment, False
                assignment[index] = value
        return assignment, True

    @staticmethod
    def __is_conjunction_or_gnd_literal(formula):
        if isinstance(formula, Conjunction):
            return reduce(lambda f: isinstance(f, GroundLit), formula , True)
        elif isinstance(formula, GroundLit):
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
                if not reduce(lambda g1, g2: g1 and g2, [isinstance(g, GroundLit) for g in disjunction.children], True):
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

    def __combine_to_dnf(self, formulas):
        #TODO: Improve implementation - First converting to cnf and then to dnf is probably not efficient (but easy^^)
        if not formulas:
            return None
        if len(formulas) == 1 and isinstance(formulas[0], GroundLit):
            return formulas[0]
        elif len(formulas) == 1:
            formulas = formulas[0]
        else:
            formulas = Conjunction(formulas, self.mln)
        if FastExact.__is_dnf(formulas):
            return formulas
        logger.warn("Formula is not in dnf, converting formula to cnf and cnf to dnf (Might cause space explosion...)")
        if not FastExact.__is_cnf(formulas):
            formulas = formulas.cnf()
        return self.__convert_cnf_to_dnf(formulas)

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
            return Disjunction([Conjunction(c, self.mln) for c in dnf_as_list], self.mln)
        else:
            raise Exception("Formula %s is not a CNF!" % str(formula))

    def __combine_formulas(self, formulas):
        def combine_formulas_from_two_iterations(iteration_0, last_iteration):
            for last_combination in last_iteration:
                for first_combination in iteration_0:
                    #TODO: Avoid squared complexity...
                    if first_combination in last_combination:
                        continue
                    conjunction = self.__combine_dnf_and_conjunctions_to_dnf(
                        last_combination.formula_conjunction, first_combination.formula_conjunction)
                    if not conjunction:
                        continue
                    yield FastExact.FormulaCombination(conjunction, None, last_combination, first_combination)

        iterations = [[FastExact.FormulaCombination(formula, index) for index, formula in enumerate(formulas)]]
        all_combinations = {}
        for combination in iterations[0]:
            if combination in all_combinations:
                all_combinations[combination].union_formulas(combination)
            else:
                all_combinations[combination] = combination
        while True:
            fixed_point_reached = True
            iterations.append([])
            for combination in combine_formulas_from_two_iterations(iterations[0], iterations[-2]):
                fixed_point_reached = False
                if combination in all_combinations:
                    all_combinations[combination].union_formulas(combination)
                else:
                    all_combinations[combination] = combination
                    iterations[-1].append(combination)
            if fixed_point_reached:
                break
        return all_combinations.keys()

    def __assign_world_number(self, combined_formulas):
        for formula in combined_formulas:
            formula.maximum_number_of_worlds = self.__get_world_count(formula.formula_conjunction)
        container_of = {}
        contained_in = set()
        for contained in combined_formulas:
            for container in combined_formulas:
                # TODO: Avoid squared complexity
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

    class FormulaCombination(object):
        def __init__(self, formula, formula_index=None, *formula_combinations):
            if formula_index and len(formula_combinations)>0 or formula_index is None and len(formula_combinations)==0:
                raise Exception("A formula combination can only be constructed from a formula xor other combinations!")
            if len(formula_combinations) == 0:
                self.__formulas = [(formula_index, formula)]
                self.__combined_formulas = formula
            else:
                self.__formulas = []
                self.__combined_formulas = formula
                for combination in formula_combinations:
                    self.union_formulas(combination)
            self.__indices_and_negation_flags = set(self.__get_indices_and_negation_flags(formula))
            self.__calculate_hash_code()
            self.__maximum_number_of_worlds = None
            self.__actual_number_of_worlds = None

        def __hash__(self):
            return self.__hash_code

        def __eq__(self, other):
            return self.indices_and_negation_flags == other.indices_and_negation_flags

        def __ne__(self, other):
            return self.indices_and_negation_flags != other.indices_and_negation_flags

        def __lt__(self, other):
            return self.indices_and_negation_flags < other.indices_and_negation_flags

        def __contains__(self, formula_combination):
            return formula_combination.formula_indices <= self.formula_indices

        def __str__(self):
            return str(self.formula_conjunction)

        def __repr__(self):
            return self.__str__()

        @property
        def formulas(self):
            return [formula.__formulas[0][1] if isinstance(Formula, FastExact.FormulaCombination) else formula
                    for index, formula in self.__formulas]

        @property
        def formula_conjunction(self):
            return self.__combined_formulas

        @property
        def formula_indices(self):
            return set([index for index, formula in self.formulas_and_indices])

        @property
        def formulas_and_indices(self):
            return self.__formulas

        @property
        def indices_and_negation_flags(self):
            return self.__indices_and_negation_flags

        @property
        def number_of_ground_atoms(self):
            return len(self.__indices_and_negation_flags)

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

        def union_formulas(self, other_formula_combination):
            own_indices = self.formula_indices
            for index, formula in other_formula_combination.formulas_and_indices:
                if not index in own_indices:
                    self.__formulas.append((index, formula))

        def __calculate_hash_code(self):
            indices = list(self.indices_and_negation_flags)
            indices.sort()
            self.__hash_code = hash(str(indices))

        def __get_indices_and_negation_flags(self, f):
            if isinstance(f, Conjunction):
                for gnd_lit in f.children:
                    if not isinstance(gnd_lit, GroundLit):
                        raise Exception("Formulas must be conjunctions of ground literals - %s is none" % gnd_lit)
                    yield gnd_lit.gndatom.idx, gnd_lit.negated
            elif isinstance(f, GroundLit):
                yield f.gndatom.idx, f.negated
            else:
                raise Exception("Formulas must be conjunctions of ground literals - %s is none" % f)