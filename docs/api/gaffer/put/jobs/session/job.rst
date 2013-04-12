PUT /jobs/<sessionid>/<jobname>
+++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Update a job configuration and relaunch processes

Resource URL
~~~~~~~~~~~~

http://localhost:5000/jobs/session/job


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**PUT** ``http://localhost:5000/jobs/test/dummy``

.. raw:: html 

    <pre class="prettyprint linenums">
    {
    "cmd": "python -u ./dummy_basic.py"
    }
    </pre>

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
        "ok": true
    } 
    </pre>

A process configuration has the following parameters:

* **name**: name of the process
* **cmd**: program command, string)
* **args**: the arguments for the command to run. Can be a list or 
  a string. 
* **env**: a mapping containing the environment variables the command
  will run with. Optional
* **uid**: int or str, user id
* **gid**: int or st, user group id,
* **cwd**: working dir
* **detach**: the process is launched but won't be monitored and
  won't exit when the manager is stopped.
* **shell**: boolean, run the script in a shell. (UNIX only)
* **redirect_output**: list of io to redict (max 2) this is a list of custom
  labels to use for the redirection. Ex: ["a", "b"] will
  redirect stdoutt & stderr and stdout events will be labeled "a"
* **redirect_input**: Boolean (False is the default). Set it if 
  you want to be able to write to stdin.
* **custom_streams**: list of additional streams that should be created 
  and passed to process. This is a list of streams labels. They become 
  available through :attr:`streams` attribute.
* **custom_channels**: list of additional channels that have been passed to
  process.

.. raw:: html

                </div>
                </div><div class="span4">
                <h4>resources informations</h4>
                <table class="table table-striped">
                <tr>
                    <td>Authentication</td>
                    <td>Require an admin</td>
                </tr>
                <tr>
                    <td>HTTP Method</td>
                    <td><strong>GET</strong></td>
                </tr>
                </table>
                </div>
            </div>            

        </div>
    </div>
