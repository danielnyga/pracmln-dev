Tools for Statistical Relation Learning
=======================================

Overview
--------

After the installation, all of these tools will be located in the 
``/path/to/pracmln/apps`` directory (which, if you've set up your 
environment correctly, is within your system ``PATH``).

Relational Data 
^^^^^^^^^^^^^^^

* ``genDB`` - the [[Database Generator|genDB Database Generator]] tool

Bayesian Logic Networks
^^^^^^^^^^^^^^^^^^^^^^^

* ``blnquery`` - the [[BLN Query Tool]], a graphical inference tool
* ``blnlearn`` - the [[BLN Learning Tool]], graphical learning tool 
* ``netEd`` - the [[Network Editor]], a graphical editor for fragment networks
* Command-line tools (invoke for usage instructions)
  
  * ``BLNinfer`` – BLN inference
  * ``BLN2MLN`` – converts BLNs to MLNs
  * ``BLNprintCPT`` – format a BLN's fragment conditional probability table for printing using LaTeX
  * ``learnABL`` – learn's BLN fragment CPTs from data

Markov Logic Networks
^^^^^^^^^^^^^^^^^^^^^

* ``mlnquery`` - the [[MLN Query Tool]], a graphical inference tool
* ``mlnlearn`` - the [[MLN Learning Tool]], a graphical learning tool
* Command-line tools (invoke for usage instructions):

  * ``MLN2WCSP`` – converts a ground Markov random field to a weighted constraint satisfaction problem (for use with toulbar2)
  * ``MLNinfer`` – inference tool 
  * ``xval`` - tool for conducting automated cross-validation with MLNs.

Bayesian Networks
^^^^^^^^^^^^^^^^^

* ``bnquery`` - the [[Bayesian Network Query Tool]], a graphical inference tool
* Command-line tools:

  * ``BNinfer`` – inference tool
  * ``BNsaveAs`` – re-saves network files in different formats
  * ``BNprintCPT`` – formats CPTs for printing using LaTeX
  * ``BNlistCPTs`` – prints a network's CPTs to stdout

Other Command-Line Tools 
^^^^^^^^^^^^^^^^^^^^^^^^

* ``jython``/``pcjython`` – Jython interpreter
* ``yprolog`` – Prolog interpreter
* ``syprolog`` – a simple yProlog interactive shell
* ``pmml2graphml`` – converts ``.pmml`` networks (Bayesian network or 
  BLN fragment network) to .graphml files that can be easily formatted
  for printing (e.g. using `yEd <http://www.yworks.com/en/products_yed_about.html>`_

Graphical Tools and Editors
---------------------------

Two graphical tools, whose usage is hopefully self-explanatory, are 
part of the package: There's an inference tool (mlnQueryTool.py) 
and a parameter learning tool (mlnLearningTool.py). Simply invoke 
them using the Python interpreter. (On Windows, do not use 
pythonw.exe to run them because the console output is an integral 
part of these tools.)::

    python mlnQueryTool.py
    python mlnLearningTool.py

General Usage
^^^^^^^^^^^^^

Both tools work with ``.mln`` and ``.db`` files in the current directory and 
will by default write output files to the current directory, too. 
(Note that when you invoke the tools, the working directory need 
not be the directory in which the tools themselves are located, 
which is why I recommend that you create appropriate shortcuts.) 
The tools are designed to be invoked from a console. Simply change 
to the directory in which the files you want to work with are 
located and then invoke the tool you want to use.

The general workflow is then as follows: You select the files you 
want to work with, edit them as needed or even create new files 
directly from within the GUI. Then you set the further options 
(e.g. the number of inference steps to take) and click on the 
button at the very bottom to start the procedure.

Once you start the actual algorithm, the tool window itself will be 
hidden as long as the job is running, while the output of the 
algorithm is written to the console for you to follow. At the 
beginning, the tools list the main input parameters for your 
convenience, and, once the task is completed, the query tool 
additionally outputs the inference results to the console (so even 
if you are using the Alchemy system, there is not really a need to 
open the results file that is generated). Configuration

You may want to modify the configuration settings in ``mlnConfig.py``:

.. note::
    If you want to use the tools to invoke the Alchemy system (more 
    than one Alchemy installation is even supported), you will have 
    to configure the paths where these installations can be found 
    as well as the set of command line switches that applies to 
    your version (they have changed over time). You can also 
    configure the file masks for MLN and database files, as well as 
    naming conventions for output files (based on input filenames 
    and settings used), which comes in handy when you are dealing 
    with more than just a handful of files. Further options concern 
    the user interface, output variants and the workflow. These are 
    documented in ``mlnConfig.py`` itself.

Integrated Editors
^^^^^^^^^^^^^^^^^^

The tools feature integrated editors for .db and .mln files. If you 
modify a file in an internal editor, it will automatically be saved 
as soon as you invoke the learning or inference method (i.e. when 
you press the button at the very bottom) or whenever you press the 
save button to the right of the dropdown menu. If you want to save 
to a different filename, you may do so by changing the filename in 
the text input directly below the editor (which is activated as 
soon as the editor content changes) and then clicking on the save 
button. Session Management

The tools will save all the settings you made whenever the learning 
or inference method is invoked, so that you can easily resume a 
session (all the information is saved to a configuration file). 
Moreover, the query tool will save context-specific information:

.. note::
    The query tool remembers the query you last made for each 
    evidence database, so when you reselect a database, the query 
    you last made with that database is automatically restored. The 
    model extension that you selected is also associated with the 
    training database (because model extensions typically serve to 
    augment the evidence, e.g. the specification of additional 
    formulas to specify virtual evidence). The additional 
    parameters you specify are saved specific to the inference 
    engine. 

Command-Line Options
^^^^^^^^^^^^^^^^^^^^

When starting the tools from the command line, they (to some degree) 
interpret and take over any Alchemy-style command line parameters, 
i.e. you can, for example, directly select the input MLN file by 
passing ``-i <mln file>`` as a command line parameter to 
``learningTool.py``. Uninterpretable options will be added to the 
"additional options" input.

Tool-Specific Fields
^^^^^^^^^^^^^^^^^^^^

Query Tool
""""""""""

* **Queries** 
  A comma-separated list of queries, where a query can be any one of the following:
  
    * a ground atom, e.g. ``foobar(X,Y)``
    * the name of a predicate, e.g. ``foobar``
    * a ground formula, e.g. ``foobar(X,Y) ^ foobar(Y,X)`` (internal engine only)

* **Max. Steps, Num. Chains** 
  The maximum number of steps to run sampling-based algorithms, and the number of parallel chains to use. If you leave the fields empty, defaults will be used.

* **Add. params** Additional parameters to pass to the inference method.

    For the internal engine, you can specify a comma-separated list 
    of assignments of parameters of the infer method you are 
    calling (refer to MLN.py for valid options.) For example, with 
    exact inference, setting debug to True (i.e. writing 
    "debug=True" into the input field) will print the entire 
    distribution over possible worlds. For MC-SAT, you could 
    specify ``debug=True, debugLevel=30`` to get a detailed log of 
    what the algorithm does (changing debugLevel will affect the 
    depth of the analysis). For J-MLNs or the Alchemy system, you 
    can simply supply additional command line parameters to pass on 
    to J-MLNs BLNinfer and Alchemy's infer respectively.
    
    
.. toctree::
   :maxdepth: 2
   
   mlnquerytool
   mlnlearningtool