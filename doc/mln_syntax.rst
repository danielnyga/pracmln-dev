
MLN Syntax and Semantics
========================

In principle, PRACMLN provides implementations of two syntaxes/grammars and two semantics of
Markov Logic Networks:

* Grammars:

  * ``StandardGrammar`` - this is the standard syntax for MLNs, which is mainly
    compatible with the Alchemy system. All constant symbols that aren't integers must begin with an upper-case letter.
    Domain symbols must begin with a lower-case letter
    Identifiers may contain only alphanumeric characters, ``-``, ``_`` and ``'``.
    All lower-case symbols are interpreted as variables.
  * ``PRACGrammar`` - a slightly modified grammar, which eases practical
    knowledge engineering of MLNs in some cases. In the ``PRACGrammar`` definitions,
    all variables in an MLN must be prefixed by ``?``, any different 
    symbol is considered a constant (upper- or lower-case).
    
* Semantics:
  
  * ``FirstOrderLogic`` - semantics of the logical formulas in the MLN
    have the meaning of classical first-order logic. They evaluate
    to either ``0`` or ``1``, depending on their truth value being ``True`` or ``False``,
    respectively.
  * ``FuzzyLogic`` - applies a fuzzy logic semantics to the logical
    formulas, i.e. the truth values of the formulas lie in the range ``[0,1]``.
    Evidence ground atoms may also take a real-valued degree of truth in ``[0,1]``. 


File Formats
------------

The file formats for MLN and database files that our Python 
implementation of MLNs processes are for the most part compatible 
with the ones used by the Alchemy system.


MLN Files
---------

An MLN file may contain:

* C++-style comments i.e. ``//`` and ``/* ... */``
* Domain declarations to assign a set of constants to a particular type/domain
  e.g. ``domFoo = {A, B, C}``
* Predicate declarations to declare a predicate and the types/domains that apply to each of its arguments
  e.g. ``myPredicate(domFoo, domBar)``.
  A predicate declaration may coincide with a rule for mutual exclusiveness and exhaustiveness (see below).

Predicate declarations
----------------------

Every predicate that is used in the MLN needs to be declared once in
the MLN file. A predicate declaration consists of the predicate name
followed by a comma-separated list of domain names of its arguments
in round brackets. For example, ::

  person(name, gender)
  
declares a predicate ``person``, which has two arguments of the domains
``name`` and ``gender``. 
 
Predicate arguments in MLNs are *typed*. This means that all predicates having
a predicate of the same domain are sharing all values of that domain.
A another predicate declaration, such as ::

  friends(name, name)
  
is defined over the same set of ``name`` s. Normally the values of the 
domains are automatically filled with the respective values that the MLN
engine finds in formulas or databases. But it is also possible to
explicitly define a domain range, for instance::

  gender = {male, female}
  
specifies that there are two possible values ``male`` and ``female``
for any predicate argument of the type ``gender``.

Sometimes it is reasonable to specify that *exactly* one out of several
atoms must always be true and all others in turn must be false. Such
constraints are called *functional* constraints since the value
of one argument is *functionally* determined by the values of the
other arguments. In PRACMLNs, this can be specified by appending an
exclamation mark ``!`` to the functionally determined argument: ::

  person(name, gender!)
  
for example specifies that for every person ``p`` in the domain of discourse,
*exactly* one out of the ground atoms ``person(p, male)`` and ``person(p, female)``
must always be true. Any possible world that violates this constraint
is automatically assigned 0 probability. Apart from that it is reasonable
to use functional constraints from a modelling point of view in many
cases, it is typically also computationally beneficial since functional
constraints result in a partial linearization of the computational
problem. In PRACMLNs, there is a second type of functional constraints,
so-called *soft functional-constraints*, that require *maximally* one
ground atom out of the set of mutually exclusive ground atoms to be true
instead of exactly one. This is very convenient for classification
problems, for instance, in order to let the probabilistic model
decline to make a decision in case of insufficient confidence, but still
exploit the computational appeal of functional constraints. Soft-functional
constraints are specified by appending a question mark ``?`` to the respective
predicate argument: ::

  class(object, class?)
  
assigns exactly one class label to an object, or none.

.. warning::

    Soft-functional constraints are extensions of the original MLN formalism
    and are not compatible with all learning and inference algorithms.



Rules for mutual exclusiveness and exhaustiveness
-------------------------------------------------

To declare that for a particular binding of some of the parameters 
of a predicate, the value assignments of the remaining parameters 
are mutually exclusive and exhaustive, i.e. that the remaining 
parameters are functionally determined by the others. For example, 
you can add the rule ``myPredicate(domFoo, domBar!)`` to declare that 
the second parameter of ``myPredicate`` is functionally determined by 
the first (i.e. that for each binding of f there is exactly one 
binding of ``b`` for which the atom is true). Formulas with attached 
weights as constraints on the set of possible worlds that is 
implicitly defined by an MLN's set of predicates and a set of 
(typed) constants with which it is combined. A formula must always 
be specified either along with a weight preceding it or, in case of 
a hard constraint, a period (``.``) succeeding it. Usually, a weight 
will be specified as a numeric constant, but when using the 
PRACMLN engine, weights can also be specified as arithmetic 
expressions, which may contain calls to functions of the Python 
math module (and the special function ``logx`` which returns -100 when 
passed 0). Note, however, that the expression must not contain any 
spaces. For example, you could specify an expression such as 
``log(4)/2`` instead of ``0.69314718055994529``. The formulas themselves 
may make use of the following operators/syntactic elements 
(operators in order of precedence): existential quantification, 
e.g. ``EXIST x myPred(x,MyConstant)`` or ``EXIST x,y (...)``. Quantification 
applies only to the formula that follows immediately after the list 
of quantified variables, so if it is a complex formula, enclose it 
in parentheses.

================= ============================================
Logical connector Example
================= ============================================
Equality          ``x=y``
Inequality        ``x=/=y`` 
Negation          ``!myPred(x,y)`` or ``!(x=y)``
Disjunction       ``myPred(x,y) v myPred(y,x)``
Conjunction       ``myPred(x,y) ^ myPred(y,x)``
Implication       ``myPred(x,y) ^ myPred(y,z) => myPred(x,z)``
Biimplication     ``myPred(x,y) <=> myPred(y,x)``
================= ============================================

When a formula that contains free variables is grounded, there will 
be a separate instance of the formula for each grounding of the 
free variables in the ground Markov network (each having the same 
weight). While the internal engine may perform a CNF conversion of 
the formulas, it does not not decompose the CNF formulas if they 
are made up of more than one conjunct in order to obtain individual 
clauses. With the internal engine, all formulas are indivisible.

Formula templates
----------------- 

An atom in a formula can be prefixed with an asterisk (``*``) to define 
a template that stands for two variants of the formula, one with 
the positive literal and one with the negative literal. (e.g. 
``*myPred(x,y)``) Moreover, you can prefix a variable that is an 
argument of an atom with a ``+`` character to define a template that 
will generate one formula for each possible binding of that 
variable to one of the domain elements applicable to that argument. 
(e.g. ``myPred(+x,y)``) 

Probability constraints on formulas (internal engine only)
----------------------------------------------------------

You may want to require that certain formulas have a fixed prior 
marginal probability regardless of the size of the domain with 
which a model is instantiated. This is accomplished by dynamically 
adjusting the weight of the formula when instantiating a ground 
Markov network. e.g.::

    P(myPred(x,y)) = 0.75

or::

    P(myPred(x,y) ^ myPred(y,x)) = 0.9 
    
Similarly, you may want to require that the 
posterior marginal probability of a ground formula be fixed. This 
essentially corresponds to a specification of soft evidence. e.g.::

    R(myPred(X,Y) v myPred(Y,X)) = 0.8

Any formulas for which a constraint is specified must also be part 
of the MLN (i.e. you must add them to the MLN, with some weight).

.. warning::

    Probability constraints are extensions of the original MLN formalism.

.. warning::
    Limitations:
    no support for functions, numbers/numeric operators or anything that is related to it
    formulas must always be preceded by a weight or be terminated by a period, even if they are only to be used in an input MLN for parameter learning
    no definition can span multiple lines


Database/Evidence files
-----------------------

A database file may contain:

* C++-style comments i.e. ``//`` and ``/* ... */``
* Positive and negative ground literals e.g. ``myPred(A,B)`` or ``!myPred(A,B)``, one per line.
* Soft/fuzzy evidence on ground atoms e.g. ``0.6 myPred(A,B)``. 

  .. warning:: Note that soft evidence is supported only the internal engine and only
      when using the inference algorithms MC-SAT (which corresponds to 
      MC-SAT-PC when using soft evidence) and IPFP-M. Note that soft 
      evidence on non-atomic formulas can be handled using posterior 
      probability constraints (see above).

* Domain extensions like domain declarations (see above); useful if you want to define constants without making any statements about them.

Databases stored in different ``.db`` files are considered *independent* of
each others by default (independent in its probabilistic meaning). Different
databases that should be treated independent can also be stored in one
single file by separating their contents by three dashes ``---`` in a single line: ::

   foo(x,y)
   bar(y,z)
   ---
   foo(a,b)
   bar(b,c)
   
represents two independent databases.


