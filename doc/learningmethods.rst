Learning Methods in PRACMLN
---------------------------

Log-likelihood Learning
^^^^^^^^^^^^^^^^^^^^^^^

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