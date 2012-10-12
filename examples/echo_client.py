from websocket import create_connection
ws = create_connection("ws://localhost:5000/wstreams/2")
ws.send("ECHO\n")
print "Sent"
print "Reeiving..."
result =  ws.recv()
print "Received '%s'" % result
ws.close()
