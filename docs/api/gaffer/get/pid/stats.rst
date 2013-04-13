GET /<pid>/stats
++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get the current statistics for a process.

Resource URL
~~~~~~~~~~~~

http://localhost:5000/pid/stats


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**GET** ``http://localhost:5000/1/stats``

.. raw:: html 

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
      "stats": {
          "mem_info1": "4M",
          "mem": 0.1,
          "mem_info2": "28M",
          "cpu": 0,
          "ctime": "0:02.15"
      }
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
