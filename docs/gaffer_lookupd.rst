gaffer_lookupd
==============

Gaffer lookupd server to register gafferd nodes and access to their
address.


$ gaffer_lookupd -h
usage: gaffer_lookupd [--version] [-v] [--daemon] [--pidfile=PIDFILE]
                      [--bind=ADDRESS] [--backlog=BACKLOG]
                      [--certfile=CERTFILE] [--keyfile=KEYFILE]
                      [--cacert=CACERT]

Options

    -h --help                   show this help message and exit
    --version                   show version and exit
    -v                          verbose mode
    --daemon                    Start gaffer in daemon mode
    --pidfile=PIDFILE
    --backlog=BACKLOG           default backlog [default: 128]
    --bind=ADDRESS              default HTTP binding [default: 0.0.0.0:5010]
    --certfile=CERTFILE         SSL certificate file
    --keyfile=KEYFILE           SSL key file
    --cacert=CACERT             SSL CA certificate
