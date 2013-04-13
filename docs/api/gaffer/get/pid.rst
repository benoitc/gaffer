GET /<pid>
++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Get the information and status of an active process. The name is
``<sessionid>.<jobname>`` . 

Resource URL
~~~~~~~~~~~~

http://localhost:5000/pid


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**GET** ``http://localhost:5000/1``

.. raw:: html 

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
      "env": {},
      "redirect_input": false,
      "pid": 1,
      "active": true,
      "cmd": "python",
      "create_time": 1365797562.9,
      "custom_streams": [],
      "commited": false,
      "os_pid": 28661,
      "name": "procfile.dummy",
      "uid": null,
      "gid": null,
      "redirect_output": [
          "out",
          "err"
      ],
      "args": [
          "-u",
          "dummy.py"
      ]
  }
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
