REST API v0.5.0 Resources
=========================


.. raw:: html

    <div class="btn-group">
        <button class="btn btn-info btn-large">Jump to</button>
        <button class="btn btn-info btn-large dropdown-toggle" data-toggle="dropdown">
            <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">

        <li><a href="#jobs">Jobs</a></li>
        <li><a href="#processes">Processes</a></li>

        <!-- dropdown menu links -->
      </ul>
    </div>



Jobs
++++

Jobs are the configurations that can be used to launch the processes in
Gaffer.


.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description</th>
    </tr>


    <tr>
    <td><a href="/jobs">GET /jobs</a>
    <td>List all jobs configuration available on this node.</td>
    </tr>
    <tr>
    <td><a href="get/jobs/resource.html">GET /jobs/resource</a></td>
    <td>Get all resources available on this machine. A resource can have
    multiple jobs defined for it. This can represent a procfile or an an
    application. The default resource is named default.</td>
    </tr>
    <tr>
    <td><a href="post/jobs/resource.html">POST /jobs/resource</a></td>
    <td>Load a new job configuration for this resource.</td>
    </tr>

    <tr>
    <td>
    <a href="get/jobs/resource/job.html">GET /jobs/resource/job</a>
    </td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="put/jobs/resource/job.html">PUT /jobs/resource/job</a>
    </td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="delete.html">DELETE /jobs/resource/job</a>
    </td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/resource/job.html">GET /jobs/resource/job/stats</a>
    </td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/resource/job.html">GET /jobs/resource/job/numprocesses</a></td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/resource/job.html">POST /jobs/resource/job/signal</a></td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="get/jobs/resource/job.html">GET /jobs/resource/job/states</a></td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/resource/job.html">POST /jobs/resource/job/states</a></td>
    <td></td>
    </tr>
    <tr>
    <td>

    <a href="get/jobs/resource/job/pids.html">GET /jobs/resource/job/pids</a></td>
    <td></td>
    </tr>
    <tr>
    <td>
    <a href="post/jobs/resource/job/commit.html">POST /jobs/resource/job/commit</a></td>
    <td></td>
    </tr>
    </table>



Processes
+++++++++


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
++++

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
++++

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description></th>
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
+++++

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description></th>
    </tr>

    <tr>
    <td><a href="get/users.html">GET /userss</a></td>
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
+++++++++++++

.. raw:: html

    <table class="table table-striped">

    <tr>
    <th>Resource</th>
    <th>Description></th>
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
