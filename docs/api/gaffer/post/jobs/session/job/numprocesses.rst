POST /jobs/<sessionid>/<jobname>/numprocesses
+++++++++++++++++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Scale the number of processes launched for a job configuration. Values
can be:

* **+N**: increase the number of processes from N
* **-N**: decrease the number of processes fron N
* **=N**: set the number of processes to N

Resource URL
~~~~~~~~~~~~

http://localhost:5000/jobs/session?job/numprocesses


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**POST** ``http://localhost:5000/jobs/test/dummy/numprocesses``

.. raw:: html 

    <pre class="prettyprint linenums">
    {
        "scale": "+1",
    }
    </pre>

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
        "numprocesses": 3
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
