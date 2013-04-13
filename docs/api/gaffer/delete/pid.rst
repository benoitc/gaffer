DELETE /<pid>
+++++++++++++++++++++++++++++++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

Stop a process.
                
Resource URL
~~~~~~~~~~~~

http://localhost:5000/pid


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**DELETE** ``http://localhost:5000/1``

.. raw:: html

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
