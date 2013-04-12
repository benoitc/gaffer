POST /jobs/<sessionid>/<jobname>/state
++++++++++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Start, Stop or Reload all processes in a job configuration
                
* **0**: stop
* **1**: start
* **2**: reload

Resource URL
~~~~~~~~~~~~

http://localhost:5000/jobs/session/job/state


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**POST** ``http://localhost:5000/jobs/test/dummy/state``

.. raw:: html 

    <pre class="prettyprint linenums">
    2 
    </pre>

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
        "ok": true 
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
