.. raw:: html

    <div class="btn-group" id="jumpnav">
        <button class="btn btn-info btn-large">Jump to</button>
        <button class="btn btn-info btn-large dropdown-toggle" data-toggle="dropdown">
            <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
        <li><a href="#jobs">Jobs</a></li>
        <li><a href="#processes">Processes</a></li>
        <li><a href="#auth">Auth</a></li>
        <li><a href="#keys">Keys</a></li>
        <li><a href="#users">Users</a></li>
        <li><a href="#miscellaneous">Miscellaneous</a></li>
      </ul>
    </div>

Gaffer REST API Resources
=========================

Jobs
----

Jobs are the configurations that can be used to launch the processes in
Gaffer.


.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>


    <tr>
    <td><a href="get/sessions.html">GET /sessions</a>
    <td>List all sessions/application available on this node.</td>
    </tr>
    <tr>
    <tr>
    <td><a href="get/jobs.html">GET /jobs</a>
    <td>List all jobs configuration available on this node.</td>
    </tr>
    <tr>
    <td><a href="get/jobs/<code>session.html">GET /jobs/<code>sessionid</code></a></td>
    <td>Get all resources available on this machine. A resource can have
    multiple jobs defined for it. This can represent a procfile or an an
    application. The default resource is named default.</td>
    </tr>
    <tr>
    <td><a href="post/jobs/session.html">POST /jobs/<code>sessionid</code></a></td>
    <td>Load a new job configuration for this resource in a session.</td>
    </tr>

    <tr>
    <td>
    <a href="get/jobs/session/job.html">GET /jobs/<code>sessionid</code>/<code>job</code></a>
    </td>
    <td>Get a job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="put/jobs/session/job.html">PUT /jobs/<code>sessionid</code>/<code>job</code></a>
    </td>
    <td>Update a job configuration.</td>
    </tr>
    <tr>
    <td>
    <a href="delete/jobs/session/job.html">DELETE /jobs/<code>sessionid</code>/<code>job</code></a>
    </td>
    <td>Unload a job configuration and stop all processes related to
    this configuration.</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/stats.html">GET /jobs/<code>sessionid</code>/<code>job</code>/stats</a>
    </td>
    <td>aggregate all processes stats for this job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/numprocesses.html">GET /jobs/<code>sessionid</code>/<code>job</code>/numprocesses</a></td>
    <td>Get the number of processes set for this job configuration</td>
    </tr>
    <td>
    <a href="post/jobs/session/job/numprocesses.html">POST /jobs/<code>sessionid</code>/<code>job</code>/numprocesses</a></td>
    <td>Increase or decrease the number of processes set for this job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job/signal.html">POST /jobs/<code>sessionid</code>/<code>job</code>/signal</a></td>
    <td>Send a signal to all processes running with this configuration</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/state.html">GET /jobs/<code>sessionid</code>/<code>job</code>/state</a></td>
    <td>Get the current job status</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job/state.html">POST /jobs/<code>sessionid</code>/<code>job</code>/state</a></td>
    <td>Start/Stop/Restart a job</td>
    </tr>
    <tr>
    <td>

    <a href="get/jobs/session/job/pids.html">GET /jobs/<code>sessionid</code>/<code>job</code>/pids</a></td>
    <td>Get all pids for a job</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job/commit.html">POST /jobs/<code>sessionid</code>/<code>job</code>/commit</a></td>
    <td>Send a one-off command to the node using a job config</td>
    </tr>
    </table>



Processes
---------

API to handle directly launched OS processes.

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/pids.html">GET /pids</a></td>
    <td>Get the list of all active processes IDs.</td>
    <tr>

    <tr>
    <td><a href="get/pid.html">GET /<code>pid</code></a></td>
    <td>Get the informations of an active process</td>
    <tr>

    <tr>
    <td><a href="delete/pid.html">DELETE /<code>pid</code></a></td>
    <td>Stop a process</td>
    <tr>

    <tr>
    <td><a href="post/pid/signal.html">POST /<code>pid</code>/signal</a></td>
    <td>Send a signal to a process</td>
    </tr>

    <tr>
    <td><a href="get/pid/stats.html">GET /<code>pid</code>/stats</a></td>
    <td>Get current statistics of a process</td>
    </tr>

    </table>


Auth
----

Authenticate to gaffer to get an authorization key. See the
:doc:`../../authenticate` documentation.

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/auth.html">GET /auth</a></td>
    <td>Send a BASIC AUTH requesGET to fetch an authorization key.</td>
    </tr>
    </table>


Keys
----

API to manage authorizations keys in a gaffer Node. The authorizations
keys give certains rights to the users in gaffer. You need to be a node
admin to access to this api.

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/keys.html">GET /keys</a></td>
    <td>List all keys available on this node</td>
    </tr>

    <tr>
    <td><a href="post/keys.html">POST /keys</a></td>
    <td>Create a new key.</td>
    </tr>

    <tr>
    <td><a href="get/keys/key.html">GET /keys/<code>key</code></a></td>
    <td>Fetch the key details.</td>
    </tr>

    <tr>
    <td><a href="delete/keys/key.html">DELETE /keys/<code>key</code></a></td>
    <td>Delete a key</td>
    </tr>

    </table>


Users
-----

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/users.html">GET /users</a></td>
    <td></td>
    </tr>

    <tr>
    <td><a href="get/users/username.html">GET /users/username</a></td>
    <td></td>
    </tr>

    <tr>
    <td><a href="put/users/username/password.html">PUT /users/username/password</a></td>
    <td></td>
    </tr>

    <tr>
    <td><a href="put/users/username/key.html">PUT /users/username/key</a></td>
    <td></td>
    </tr>

    </table>



Miscellaneous
-------------

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/index.html">GET /</a></td>
    <td>Return gaffer main informations</td>
    </tr>

    <tr>
    <td><a href="get/ping.html">GET /ping</a></td>
    <td>Ping a gaffer return. Useful to test it the nide is alive.</td>
    </tr>

    <tr>
    <td><a href="get/version.html">GET /version</a></td>
    <td>Return the gaffer version</td>
    </tr>

    </table>


.. toctree::
    :hidden:
    :glob:

    get/*
    get/jobs/*
    get/jobs/session/*
    get/jobs/session/job/*
    get/pid/*
    post/*
    post/jobs/*
    post/jobs/session/job/*
    post/pid/*
    put/get/*
    put/jobs/*
    put/jobs/session/*
    delete/*
    delete/jobs/*
    delete/jobs/session/*
