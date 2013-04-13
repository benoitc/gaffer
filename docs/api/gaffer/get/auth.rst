GET /auth
++++++++++

.. raw:: html

    <ul class="nav nav-tabs">
    <li class="active"><a href="#view">View</a></li>
    </ul>
    <div class="tab-content">
        <div class="tab-pane active" id="home">
            <div class="row-fluid">
                <div class="span8">

make an HTTP BASIC Auth request to get an authorization key
                
Resource URL
~~~~~~~~~~~~

http://localhost:5000/auth


Parameters
~~~~~~~~~~

None

.. raw:: html
    
    <h4>Example of request</h4>

**GET** ``http://localhost:5000/auth``

.. raw:: html 

    <pre class="prettyprint linenums">
    Authorization: Basic YmVub2l0Yzp0ZXN0
    User-Agent: curl/7.29.0
    Host: localhost:5000
    Accept: */*

    </pre>

    <h4>Response</h4>
    <pre class="prettyprint linenums">
    {
        "api_key": 5fd6a44b51714cd0bb29dd64f0a6cbbb
    } 
    </pre>

    <h4>Status Errors</h4>

* **200**: OK
* **401**: Unauthorized

.. raw:: html

                </div>
                </div><div class="span4">
                <h4>resources informations</h4>
                <table class="table table-striped">
                <tr>
                    <td>Authorization</td>
                    <td>all</td>
                </tr>
                <tr>
                    <td>HTTP Method</td>
                    <td><strong>GET</strong></td>
                </tr>
                <tr>
                    <td>Status Codes</td>
                    <td>
                    200, 401
                    </td>
                </tr>
                </table>
                </div>
            </div>            

        </div>
    </div>
