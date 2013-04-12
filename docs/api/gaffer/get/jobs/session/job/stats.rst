GET /jobs/<sessionid>/<jobname>/stats
+++++++++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get statistics of all processes for a job configuration.

Resource URL
~~~~~~~~~~~~

http://localhost:8000/jobs/sessionid/jobname

Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>


**GET** ``http://localhost:5000/jobs/procfile/dummy/stats`` 


.. raw:: html 

    <pre class="prettyprint linenums">
    {
        "cpu": 0,
        "stats": [
            {
                "cpu": 0,
                "ctime": "0:00.30",
                "mem_info1": "5M",
                "os_pid": 26089,
                "mem_info2": "28M",
                "mem": 0.2,
                "pid": 1
            },
            {
                "cpu": 0,
                "ctime": "0:00.20",
                "mem_info1": "5M",
                "os_pid": 26101,
                "mem_info2": "28M",
                "mem": 0.2,
                "pid": 4
            }
        ],
        "max_mem": 0.2,
        "name": "procfile.dummy",
        "max_cpu": 0,
        "mem": 0.4,
        "min_mem": 0.2,
        "min_cpu": 0
    }
    </pre>

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
