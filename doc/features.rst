
Feature Overview
================

Statistical Relational Models
-----------------------------

Bayesian Logic Networks (BLNs) [Java]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Inference (posterior marginals)

  * Sampling Methods
  
    * Likelihood Weighting
    * Backward Simulation
    * SampleSearch
    
  * Message-Passing Methods
  
    * Iterative join-graph propagation (IJGP)
    * (Loopy) Belief Propagation
    
  * Exact Methods
    
    * ACE
    * Enumeration-Ask
    * Variable Elimination
    * Pearl's Algorithm (with join-tree clustering)
    
  * Markov Chain Monte Carlo Methods
    
    * MC-SAT
    * Gibbs Sampling
    * ...and quite a few more
    
* Learning (maximum likelihood)
* Translation to MLNs
* Graphical Learning and Inference Tools

Adaptive Markov Logic Networks (AMLNs) [Python]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Inference (posterior marginal probabilties of formulas)

  * MC-SAT
  * Gibbs Sampling
  * enumeration (exact)

* Probabilistic Inference with Uncertain Evidence (Soft Evidential Update)

  * MC-SAT-PC
  * IPFP-M (iterative proportional fitting)

* Inference (most probable explanation)

  * MaxWalkSAT

* Learning

  * maximum pseudo-likelihood
  * maximum likelihood

* Knowledge Representation
  * Cardinality restrictions (count constraints)
  * Constraints on (prior) marginal probabilities of formulas
  * Constraints on posterior probabilities of ground atoms and formulas (soft evidence)

Markov Logic Networks [Java]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Inference (posterior marginals of ground atoms)

  * MC-SAT
* Inference (most probable explanation)

  * MaxWalkSAT
  * `Toulbar2 <https://mulcyber.toulouse.inra.fr/projects/toulbar2>`_ Branch-&-Bound

* Translation to WCSPs (weighted contraint satisfaction problems)

Unified Interfaces to Relational Models and Data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Model Abstraction: unified interface to statistical relational models

  * in the ``probcog`` Java library (and the matching ``jyprobcog`` Jython scripting library)
  * in a YARP service 
  * in a ROS node

* Data Collection

  * ''srldb'' library for working with relational data (Java/Jython); features:
    * automatic generation of training databases in various formats 
    * automatic discretization of continuous data
    * generation of basic MLN/BLN models (containing all the necessary declarations) as a starting point for learning problems

  * Generation of synthetic relational data: library for convenient scripting of relational stochastic processes

Probabilistic Graphical Models
------------------------------

Bayesian Networks [Java]
^^^^^^^^^^^^^^^^^^^^^^^^

* Support for various file formats

  * import: Bayesian Interchange Format (XML-BIF), Ergo/UAI, PMML 3 (extended)
  * export: Bayesian Interchange Format (XML-BIF), Ergo/UAI, PMML 3 (extended), Hugin

* Inference

  * Sampling Methods

    * Likelihood Weighting
    * Backward Simulation
    * SampleSearch

  * Message-Passing Methods

    * Iterative join-graph propagation (IJGP)
    * (Loopy) Belief Propagation

  * Exact Methods

    * ACE
    * Enumeration-Ask
    * Variable Elimination
    * Pearl's Algorithm

  * Markov Chain Monte Carlo Methods

    * MC-SAT
    * Gibbs Sampling

  * ...and quite a few more

* Learning (maximum likelihood)

Our implementation is based on BNJ (Bayesian Network Tools in Java).