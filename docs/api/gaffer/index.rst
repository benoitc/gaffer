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
    <td><a href="get/jobs/session.html">GET /jobs/session</a></td>
    <td>Get all resources available on this machine. A resource can have
    multiple jobs defined for it. This can represent a procfile or an an
    application. The default resource is named default.</td>
    </tr>
    <tr>
    <td><a href="post/jobs/session.html">POST /jobs/session</a></td>
    <td>Load a new job configuration for this resource in a session.</td>
    </tr>

    <tr>
    <td>
    <a href="get/jobs/session/job.html">GET /jobs/session/job</a>
    </td>
    <td>Get a job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="put/jobs/session/job.html">PUT /jobs/session/job</a>
    </td>
    <td>Load a job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="delete/jobs/session/job.html">DELETE /jobs/session/job</a>
    </td>
    <td>Unload a job configuration and stop all processes related to
    this configuration.</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/stats.html">GET /jobs/session/job/stats</a>
    </td>
    <td>aggregate all processes stats for this job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/numprocesses.html">GET /jobs/session/job/numprocesses</a></td>
    <td>Get the number of processes set for this job configuration</td>
    </tr>
    <td>
    <a href="post/jobs/session/job/numprocesses.html">POST /jobs/session/job/numprocesses</a></td>
    <td>Increase or decreqse the number of processes set for this job configuration</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job/signal.html">POST /jobs/session/job/signal</a></td>
    <td>Send a signal to all processes running with this configuration</td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/session/job/states.html">GET /jobs/session/job/states</a></td>
    <td>Get the current job status</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job.html">POST /jobs/session/job/states</a></td>
    <td>Start/Stop/Restart a job</td>
    </tr>
    <tr>
    <td>

    <a href="get/jobs/session/job/pids.html">GET /jobs/session/job/pids</a></td>
    <td>Get all pids for a job</td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/session/job/commit.html">POST /jobs/session/job/commit</a></td>
    <td>Send a one-off command to the node using a job config</td>
    </tr>
    </table>



Processes
---------

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>


    <tr>
    <td><a href="/get/pid.html">GET /pid</a></td>
    <td></td>
    <tr>


    <tr>
    <td><a href="post/pid/signa.htmll">POST /pid/signal</a></td>
    <td></td>
    </tr>

    <tr>
    <td><a href="post/pid/stats.html">POST /pid/stats</a></td>
    <td></td>
    </tr>

    </table>


Auth
----

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="post/auth.html">POST /auth</a></td>
    <td></td>
    </tr>
    </table>


Keys
----

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>

    <tr>
    <td><a href="get/keys.html">GET /keys</a></td>
    <td></td>
    </tr>

    <tr>
    <td><a href="get/keys/id.html">GET /keys/id</a></td>
    <td></td>
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
    post/*
    post/jobs/*
    post/jobs/session/*
    put/get/*
    put/jobs/*
    put/jobs/session/*
    delete/*
    delete/jobs/*
    delete/jobs/session/*
