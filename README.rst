==========================================
 Aerostat - Automated Naming for the Cloud
==========================================

:Version: 1.0.11
:Web: http://github.com/urbanairship/aerostat
:Download: http://pypi.python.org/pypi/aerostat/
:Source: http://github.com/urbanairship/aerostat/
:Keywords: naming, ec2, configuration management, mongodb, python, git

.. _Aerostat-synopsis:

Aerostat is an open source client/server system for automatically naming
cloud nodes based on the service that they run primarily. This is a key piece
of automating deployment of new nodes. 

It's designed with Amazon EC2 in mind, however, it should be extendable to any cloud
provider. It should be noted that Aerostat is still under active development. While
it is in production at urbanairship.com, there are a number of scenarios in which
it may not work with other infrastructure. Consider this beta software.

The distribution of node identification (hostnames, aliases) happens by using 
/etc/hosts. So this software is designed for Unix systems which rely on that file
during routine DNS resolution.

The central Aerostat server is a thin wrapper around MongoDB. The serve code is
responsible for making sure that EC2 and Aerostat's database agree on which instances
are alive. Having a running MongoDB server is a prerequisite for using Aerostat.

.. contents::
    :local:

.. _Aerostat-overview:

Overview
========

This is a high level overview of the architecture.

.. image:: http://dl.dropbox.com/u/5586906/images/aerostatOverview.png

* **Aerostat_Server** deals with making sure that the Aerostat's MongoDB reflects the outside world (machine state in the cloud provider, or configuration information from developers).
* **Aerostat Registrar** deals with getting a new node a name assignment. It also handles master name changes.
* **Aerostat Updater** deals with updating /etc/hosts on the node.


.. _Aerostat-features:

Features
========

    +-----------------+----------------------------------------------------+
    | Registration    | Clients can choose to register with the Aerostat   |
    |                 | server, registration includes picking a new name   |
    |                 | and setting the hostname of the local system.      |
    +-----------------+----------------------------------------------------+
    | Updating        | Aerostat clients can then be run such that they    |
    |                 | refresh the information in /etc/hosts. It's helpful|
    |                 | to run Aerostat in daemon mode for this.           |
    +-----------------+----------------------------------------------------+
    | Master-Naming   | Use <service>-master for masterful services. After |
    |                 | first node is created for this service, all others |
    |                 | take up names like <service>-slave-1, etc.         | 
    |                 | New hosts always fill gaps.                        |
    +-----------------+----------------------------------------------------+
    | Iterative-Naming| Use <service>-N for services, where N is the number|
    |                 | of the node in question. Ex. <service>-0, etc.     |
    |                 | Iterative names are 0 indexes, whereas Masterful is|
    |                 | not.                                               |
    +-----------------+----------------------------------------------------+
    | Master          | Masterful services can "swap" the master node with |
    | Change-Over     | one of the slaves. This is initiated from the      |
    |                 | slave. Old master negotiates for lowest possible   |
    |                 | slave number.                                      |
    +-----------------+----------------------------------------------------+
    | Gap Filling     | When new nodes come online, or there is a change in|
    |                 | mastership, the new node will use the name of a    |
    |                 | missing node                                       |
    +-----------------+----------------------------------------------------+
    | Daemon Mode     | Run as a daemon to get continual updates.          |
    +-----------------+----------------------------------------------------+
    | Legacy Updates  | If you've used a similar service in the past to    |
    |                 | update /etc/hosts, you can preserve that           |
    |                 | functionality while transitioning to Aerostat by   |
    |                 | specifying --legacy-updater and the path to the    |
    |                 | script.                                            |
    +-----------------+----------------------------------------------------+

.. _Aerostat-example:

Example Usage
=============

Initial Setup
-------------

There are a few expectations that Aerostat has about how to get around in your infrastructure. 

For the Aerostat Server
~~~~~~~~~~~~~~~~~~~~~~~

* MongoDB running on a node which is known within the Aerostat system as ``admin-master``, or with whatever you wish to override (using --server).
* Authentication information for AWS EC2 is located in a file, which by default is in ``/root/installer/.ec2``. The expectation is that the file is formatted into three lines, consisting of ``key_id``, ``key_secret``, and ``keypair_name`` (optional). Eventually, this will be included as a proper config file.
* If you're planning on using the git repo to Aerostat configuration management, make sure that the directory path for Aerostat's local repo exists, that the credentials for accessing the origin master repository work and that the URL is accurate. 

With Supervisord
-----------------

Aerostat is designed to be run behind supervisord or some other daemon management framework. Here's an example supervisord.conf snippet for an Aerostat server running in production.  

From supervisord.conf for the Aerostat server itself.

|    [program:aerostat]
|    command=/usr/local/bin/aerostat --update --daemon --server=localhost --loglevel=DEBUG
|    user=root
|
|    [program:aerostatd]
|    command=/usr/local/bin/aerostatd
|    user=root

From a client node in the cluster:

|    [program:aerostat]
|    command=/usr/local/bin/aerostat --update --daemon --loglevel=DEBUG
|    user=root

Note, there's no need to specify the server to connect to, because it defaults to 'admin-master' in the local cluster.

With Commandline
----------------

The basic help: 

    gavin@admin-master-test:~$ aerostat --help
    Usage: aerostat [options] arg1 arg2

    Options:
      -h, --help            show this help message and exit
      --register            Register server as a new Aerostat Client.
      --change-master       Make current host the master for its service.
      --update              Update /etc/hosts.
      --server=SERVER       hostname of Aerostat/mongo server to connect to.
      --daemon              Whether or not to run service (update) as a daemon.
      --loglevel=LOGLEVEL   Which severity of log to display.
      --legacy-updater=LEGACY
                            Specify path. Run legacy naming service prior to
                            Aerostat.
      --dryrun              Whether or not to actually carry our registration and
                            updates.
      --offline             Whether or not we should connect to AWS for
                            information.

Good options for a test run on your workstation might look like this:

    # aerostat --server=localhost --dryrun --offline --update

or 

    # aerosat --server=localhost --dryrun --offline --register

Of course, this requires that you have MongoDB, installed, running and that you don't have authorization restrictions. To enable authorization restrictions, you'll want to define that yourself in a subclasses Aerostat module where db_connect is overridden.

As a Library
------------

Most of the general purpose functions for other system administration tools are located in the ``aerostat.aerostat`` module as module-level functions. This includes:

* db_connect
* db_disconnect
* get_aws_data
* hostname_exists(hostname)
* get_hostname(instance_id)
* get_master(service)
* check_master(service, instance_id)


.. _Aerostat-documentation:

Documentation
=============

Server Side
-----------

In ``aerostat.aerosat_server.py`` configuration information is read from a yaml file and if appropraite values are found sets instance variables. For the most part, all the aerostat_server module does is remove a node from aerostat's mongodb collection when it's not in a running state according to AWS.


Client Side
-----------
A couple of useful options for testing are –dryrun, and –offline supplied to the Aerostat client.

* ``-–dryrun`` means that it will go through the process of either registering, changing master, or updating the /etc/hosts, but won't actually do so. Instead it just logs what it would have done.
* ``-–offline`` means that it won't try to connect to AWS. Instead it just fakes instance_id information (using the string 'test-instance').
* ``-–server`` allows you to specify which Aerostat (or MongoDB) server to connect to. Set this to localhost if you want to do testing locally.

Registrar
~~~~~~~~~

The registration flow starts with Aerostat reading: ``service_name``, ``service_type``, ``*args`` (where all args are aliases for the system's name). These data are read from a file located ``/etc/aerosat_info``. The attributes are space delimited, and the only required one is the ``service_name`` (``service_type`` is assumed to be iterative if left blank).

Most of the interesting things happen in this class; this is where the hostname gets picked, gaps in contiguous hostnames get filled, etc. This is also where master failovers can happen.

Master Failover
~~~~~~~~~~~~~~~

At this time, master failover is triggered from the client that you wish to promote to master. It looks like this:

    node# aerostat --change-master

This checks to see:

* if the service is masterful
* if the host is already master.
* if current host is not master, then it takes the <service>-master hostname and the old master that it replaces goes through the same process as a new node (therefore filling any gaps that might exist).

Note: because we don't have direct access to both systems whose names are changing, we don't actually change the hostname. This is something that I'd like to implement in the near future (e.g. when an update is performed and your Aerostat name doesn't match your hostname, change the hostname).

Updater
~~~~~~~

This is probably the simplest portion of Aerostat. Basically, it just queries the Aerostat server, constructs its dataset of IP to hostname resolution (and aliases) and then writes that to a temporary file. If all goes well there, then it moves it over the existing ``/etc/hosts`` file.

It gets complicated when services require a legacy updating system. In that case, the ``-–legacy-updater`` option allows you to specify a binary that it expects to write out to a file called ``/etc/hosts.legacy``. Then Aerostat will concatenate all of that legacy data, plus the Aerostat data into ``/etc/hosts.tmp``. If that works out, then it overwrites ``/etc/hosts`` like normal.

Since DNS queries that hit ``/etc/hosts`` will take whichever value they find first, putting the legacy data at the top of the file makes sure that there are no breaking conflicts from the legacy naming system.

.. _Aerostat-installation:

Installation
============

You can install ``aerostat`` either via the Python Package Index (PyPI)
or from source.

To install using ``pip``:

    $ pip install aerostat

To install using ``easy_install``:

    $ easy_install aerostat

.. _Aerostat-installing-from-source:

Downloading and installing from source
--------------------------------------

Download the latest version of ``aerostat`` from
http://pypi.python.org/pypi/aerostat/

You can install it by doing the following:

    $ tar xvfz aerostat-0.0.0.tar.gz
    $ cd aerostat-0.0.0
    $ python setup.py build
    # python setup.py install # as root

.. _Aerostat-installing-from-git:

Using the development version
-----------------------------

You can clone the repository by doing the following:

    $ git clone git://github.com/urbanairship/aerostat.git


Running tests
-------------

Tests work with either nosetests or py.test as long as the package is
installed:

    $ python setup.py develop
    $ nosetests # or...
    $ py.test


.. _getting-help:

Bug tracker
===========

If you have any suggestions, bug reports or annoyances please report them
to our issue tracker at http://github.com/urbanairship/aerostat/issues/

.. _contributing:

Contributing
============

Development of ``Aerostat`` happens at Github: http://github.com/urbanairship/aerostat

.. _license:

License
=======

This software is licensed under the ``MIT``. See the ``LICENSE``
file in the top distribution directory for the full license text.

.. # vim: syntax=rst expandtab tabstop=4 shiftwidth=4 shiftround

