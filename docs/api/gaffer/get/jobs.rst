GET /jobs
+++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get the list of all jobs configurations loaded on this node. A job
describe how a process can be launched on the machine. Each jobs are
prefixed by the session name: ``<session>.<jobname>``.

Resource URL
~~~~~~~~~~~~

http://localhost:5000/jobs


Parameters
~~~~~~~~~~

None


.. raw:: html
    
    <h4>Example of request</h4>


**GET** ``http://localhost:5000/jobs`` 

.. raw:: html 

    <pre class="prettyprint linenums">
     {
        "jobs": [
            "procfile.dummy",
            "procfile.dummy1",
            "procfile.echo"
        ]
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
