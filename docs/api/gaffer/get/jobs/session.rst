GET /jobs/<sessionid>
+++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get all jobs from a session

Resource URL
~~~~~~~~~~~~

http://localhost:8000/jobs/sessionid


Parameters
~~~~~~~~~~

None


.. raw:: html
    
    <h4>Example of request</h4>


**GET** ``http://localhost:5000/jobs/procfile`` 


.. code-block:: json
    :linenos:

     {
        "jobs": [
            "procfile.dummy",
            "procfile.dummy1",
            "procfile.echo"
        ],
        "sessionid": "procfile"
    }


.. raw:: html

                </div>
                </div><div class="span4">
                <h4>resources informations</h4>
                <table class="table table-striped">
                <tr>
                    <td>Authentication</td>
                    <td>Require an admin or a session manager</td>
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
