POST /jobs/<sessionid>/<jobname>/commit
+++++++++++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Send a one-off command to gaffer using a job configuration. Commited
jobs aren't supervised, they will run until they die but won't be
restarted. You can pass to the command a different environment and the
graceful timeout. It return the ID of the process launched.
                
Resource URL
~~~~~~~~~~~~

http://localhost:5000/jobs/session/job/commit


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**POST** ``http://localhost:5000/jobs/test/dummy/commit``

.. raw:: html 

    <pre class="prettyprint linenums">
    {
        "env": {},
        "graceful_timeout": 0
    }
    </pre>

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
        "pid": 10
    } 
    </pre>

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
