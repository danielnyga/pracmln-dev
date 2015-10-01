Learning Methods
----------------

.. autoclass:: pracmln.MLNLearn
    :members: mln, db, output_filename, params, method, pattern, use_prior, prior_mean,
              prior_stdev, incremental, shuffle, use_initial_weights, qpreds, epreds,
              discr_preds, logic, grammar, multicore, profile, verbose, ignore_unknown_preds,
              ignore_zero_weight_formulas, save

The above parameters are common for all learning algorithms. In 
addition, specific parameters can be handed over to specific 
algorithms, which will be introduced in the following.


Log-likelihood Learning
^^^^^^^^^^^^^^^^^^^^^^^

The standard learning method using maximum likelihood.

Additional parameters:

*none*

Discriminative log-likelihood Learning
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Standard log-likelih

Pseudo-likelihood Learning
^^^^^^^^^^^^^^^^^^^^^^^^^^

Composite-likelihood Learning
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Optimization Techniques
-----------------------

In addition to the learning method, different optimization techniques
can be specified in PRACMLNs. The type of the optimizer and their
parameters can be specified in the additional parameters text field
in the :doc:`mlnlearningtool` by specifying a parameter ``optimizer=<algo>``.
Currently, the following optimization techniques are supported.

BFGS (Broyden–Fletcher–Goldfarb–Shanno algorithm)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Command: ``optimizer='bfgs'``
* Additional Parameters:
   *  ``maxiter=<int>``: Specifies the maximal number of gradient ascent steps.

.. note::

    This is the standard SciPy implementation

Conjugate Gradient
^^^^^^^^^^^^^^^^^^

* Command: ``optimizer='cg'``
* Additional Parameters:
   *  ``maxiter=<int>``: Specifies the maximal number of gradient ascent steps.

.. note::

    This is the standard SciPy implementation



Particle Swarm Optimization 
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Command; ``optimizer='pso'``
* Additional Parameters:

TODO: some description

.. note::

    This is the PlayDoh implementation that can be distributied over the network...
    TODO describe how this can be done.


Genetic Algorithms 
^^^^^^^^^^^^^^^^^^

* Command; ``command='pso'``
* Additional Parameters:

TODO: some description