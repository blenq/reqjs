Getting Started
===============

Installation
------------

The reqjs package can be retrieved from
`GitHub <https://github.com/blenq/reqjs>`_.
It can be installed directly, for example using pip.

.. code-block:: console

    $ pip install git+https://github.com/blenq/reqjs.git

Local build
-----------

It can be built locally by first checking out the code

.. code-block:: console

    $ git clone https://github.com/blenq/reqjs.git
    $ cd reqjs
    $ git submodule init
    $ git submodule update

and then build it using any build frontend, for example

.. code-block:: console

    $ pip install build
    $ python -m build
