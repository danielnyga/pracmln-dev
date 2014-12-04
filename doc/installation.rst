
Getting Started
===============

Compatibility
-------------

This software suite works out-of-the-box on Linux/AMD64, Linux/i386 
and Windows/32bit. 

For other environments, you will need to obtain an appropriate binary package 
of the Standard Widget Toolkit library (http://www.eclipse.org/swt/) and modify 
the application files created during installation (see below) to use them.

Prerequisites 
-------------

* Java 5 runtime environment (or newer)

* Python 2.5 (or newer) with Tkinter installed
  Note: On Windows, Tkinter is usually shipped with Python. 
  On Linux, the following packages should be installed (tested for Ubuntu)::
  
    sudo apt-get install python-tk python-scipy python-pyparsing

* For MPE (most probable explanation) inference on MLNs, the ``toulbar2``
  WCSP solver is required. It can be obtained from::
  
    https://mulcyber.toulouse.inra.fr/projects/toulbar2
    
  Its executable ``toulbar2`` should be included in ``$PATH``.

Installation
------------

#. Generating Apps

   Run the ``make_apps`` script: ::
    
    python make_apps.py

   This will generate a number of shell scripts (or batch files for Windows) in the ``./apps`` directory. 

#. Setting up your Environment

   ``make_apps`` will report how to set up your environment.
   
   To temporarily configure your environment, you can simply use the ``env`` script/batch
   file it creates to get everything set up.
   If you use ProbCog a lot, consider adding the ``./apps`` directory to your ``PATH`` variable
   or copy the files created therein to an appropriate directory.
   If you intend to make use of scripting, also set ``PYTHONPATH`` and ``JYTHONPATH`` as described
   by ``make_apps``.

C++ bindings
------------

* Requirements:

 * Linux OS (tested on Ubuntu 14.04)

 * libboost-python

 * libpython-dev

* Installation:

 * Run the ``make_apps`` script with ``--cppbindings``: ::

    python make_apps.py --cppbindings

* Usage:

 * Include the header ``pracmln/mln.h`` and link against ``libpracmln``

 * A simple example program ::

    #include <pracmln/mln.h>

    int main(int argc, char **argv)
    {
      // create a mln object
      MLN mln;

      // initialize the object (loading python packages, etc.)
      if(!mln.initialize()){
        // error
      }

      std::vector<std::string> query;
      query.push_back("some query");

      // change settings, give input files, etc.
      mln.setQuery(query);
      mln.setMLN("path to mln file");
      mln.setDB("path to db file");

      std::vector<std::string> results;
      std::vector<double> probabilities;

      // execute inference
      if(mln.infer(results, probabilities)){
        // error
      }

      // do something with the results

      return 0;
    }

Examples
--------

There are example models in the ``./examples/`` directory.

Simply run the ``blnquery`` or ``mlnquery`` applications in one of the subdirectories
to try out some inference tasks.

In the ``./examples/meals/`` directory, you can also try out learning.
To train a BLN or MLN model run ``blnlearn`` or ``mlnlearn``. 
