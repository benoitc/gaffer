GET /sessions
+++++++++++++


.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get the list of all resources loaded on this node. A resource is a
collection of job configuration. It is generally corresponding to the
list of jobs needed for an application.

Resource URL
~~~~~~~~~~~~

http://localhost:8000/sessions


Parameters
~~~~~~~~~~

None


.. raw:: html
    
    <h4>Example of request</h4>


**GET** ``http://localhost:5000/sessions`` 

.. raw:: html 

    <pre class="prettyprint linenums">
    {
        "sessions": [
            "procfile"
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
