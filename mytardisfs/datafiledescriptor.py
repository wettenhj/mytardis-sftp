# Client program to request file descriptor for MyTardis data file.
import socket
import fdsend
import os
import subprocess
import time
import tempfile

class MyTardisDatafileDescriptor:

    def __init__(self, message=None, fileDescriptor=None):
        self.message = message
        self.fileDescriptor = fileDescriptor

    @staticmethod
    def get_file_descriptor(experimentId, datafileId):

        # Determine the absolute path of the socket for interprocess communication:
        f = tempfile.NamedTemporaryFile(delete=True)
        socketPath = f.name
        f.close()

        proc = subprocess.Popen(["sudo","-u","mytardis","af_unix_socket_server", \
                socketPath, str(experimentId), str(datafileId)], \
                stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        while not os.path.exists(socketPath):
            time.sleep(0.01)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socketPath)
        sock.send("Request file descriptor")
        (message, fileDescriptors) = fdsend.recvfds(sock, 128, numfds = 1)
        sock.close()

        fileDescriptor = None
        if len(fileDescriptors)>0:
            fileDescriptor = fileDescriptors[0]

        return MyTardisDatafileDescriptor(message,fileDescriptor)

if __name__ == "__main__":
    experimentId = "73"
    print "Experiment ID: " + experimentId
    #datafileId = "1463"
    datafileId = "6680"
    print "Datafile ID: " + datafileId

    myTardisDatafileDescriptor = MyTardisDatafileDescriptor.get_file_descriptor(experimentId, datafileId)
    if myTardisDatafileDescriptor.fileDescriptor is not None:
        print "Message: " + myTardisDatafileDescriptor.message

        fileDescriptor = myTardisDatafileDescriptor.fileDescriptor 
        fileHandle = os.fdopen(fileDescriptor)
        print "File content: " + fileHandle.read(1024) # Only show first 1024 bytes for now.
        fileHandle.close()

