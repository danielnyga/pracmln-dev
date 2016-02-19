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
from pracmln.logic.fol import Conjunction, GroundLit, TrueFalse, Disjunction
from numpy import exp
from operator import mul

logger = logging.getLogger(__name__)


class FastExact(Inference):
    def __init__(self, mrf, queries, **params):
        Inference.__init__(self, mrf, queries, **params)

    def _run(self):
        ground_formulas, evidence = self.__get_ground_formulas()
        logger.info("Grounding finished!")
        non_weight_one_worlds = self.__get_non_weight_one_worlds(ground_formulas, self.queries, evidence)
        to_return = {query: self.__calculate_probability(ground_formulas, query, evidence,
                                                    non_weight_one_worlds.query_worlds_dict[query],
                                                    non_weight_one_worlds.evidence_worlds)
                for query in self.queries}
        print(to_return)
        return to_return

    class _NonWeightOneWorldCollection(object):
        def __init__(self, queries):
            self.evidence_worlds = []
            self.query_worlds_dict = {q: [] for q in queries}

    def __get_world_as_formula(self, world):
        logical_evidence = []
        for i in range(0, len(world)):
            if world[i] is not None:
                if world[i] != 1 and world[i] != 0:
                    raise Exception("Unknown Probability value: " + str(world[i]))
                logical_evidence.append(GroundLit(self.mrf.gndatom(i), world[i] == 0, self.mrf.mln))
        return None if not logical_evidence else Conjunction(logical_evidence, self.mrf.mln)

    def __get_non_weight_one_worlds(self, non_hard_formulas, queries, evidence):
        to_return = self._NonWeightOneWorldCollection(queries)
        for formula in non_hard_formulas:
            to_return.evidence_worlds += self.__get_worlds_satisfying_formula(formula)
            for query in queries:
                query_generator = self.__combine_dnf_and_conjunctions_to_dnf(query, formula)
                if query_generator is not None:
                    to_return.query_worlds_dict[query] += self.__get_worlds_satisfying_formula(query_generator)
        return to_return

    def __get_ground_formulas(self):
        formulas = list(self.mrf.formulas)
        evidence = self.__get_world_as_formula(self.mrf.evidence)
        if evidence:
            evidence.weight = HARD
            formulas.append(evidence)
        grounder = FastExistentialGrounding(self.mrf, False, False, formulas, -1)
        ground_formulas = list(grounder.itergroundings())
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
        if not FastExact.__is_dnf(dnf):
            raise Exception("Formula %s is not in dnf and neither a Conjunction nor a Ground Literal!" % dnf)
        formulas_compatible_with_evidence = []
        for formula in conjunctions:
            variable_assignment, consistent = self.__check_consistency_and_get_world(formula)
            if not consistent:
                continue
            if not dnf:
                formulas_compatible_with_evidence.append(formula)
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
                else:
                    raise Exception("One of the following ground formulas is not a conjunction: %s or %s" %
                                    (formula, sub_formula))
                formulas_compatible_with_evidence.append(Conjunction(ground_literals, self.mrf.mln, formula.idx))
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

    def __get_worlds_satisfying_formula(self, formula):
        world_restriction = self.__get_dnf_as_dict_of_truth_values(formula)
        if world_restriction is None:
            return []

        def evaluate_variable(variables, old_world):
            if not variables:
                yield old_world
            else:
                variable = variables[0]
                other_variables = variables[1:]
                for _, world in variable.iterworlds(old_world):
                    for child_world in evaluate_variable(other_variables, world):
                        yield child_world

        return reduce(lambda l1,l2: l1+l2,
                      [list(evaluate_variable(self.mrf.variables, wr)) for wr in world_restriction],
                      [])

    def __calculate_probability(self, ground_formulas, query, evidence, query_worlds, evidence_worlds):
        # TODO: Exact formulas are not handled correctly: Worlds violating hard formulas must have probability 0
        # TODO: What if no worlds match the evidence? div by zero?
        def get_world_probability(worlds):
            return sum([exp(sum([gf.weight * gf(w) for gf in ground_formulas])) for w in worlds])
        return (
                   self.__get_world_count(self.__combine_dnf_and_conjunctions_to_dnf(evidence, query)) - \
                   len(query_worlds) + \
                   get_world_probability(query_worlds)
               ) \
               * 1.0 / \
               (
                    self.__get_world_count(evidence) - \
                    len(evidence_worlds) + \
                    get_world_probability(evidence_worlds)
               )

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
            return []
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
            raise Exception("Formula %s is not a CNF!", str(formula))

