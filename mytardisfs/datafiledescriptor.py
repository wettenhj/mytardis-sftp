# Client program to request file descriptor for MyTardis data file.
import socket
import fdsend
import os
import subprocess
import time
import tempfile


class MyTardisDatafileDescriptor:

    def __init__(self, message=None, file_descriptor=None):
        self.message = message
        self.file_descriptor = file_descriptor

    @staticmethod
    def get_file_descriptor(mytardis_install_dir, auth_provider,
                            experiment_id, datafile_id):

        # Determine the absolute path of the socket
        # for interprocess communication:
        f = tempfile.NamedTemporaryFile(delete=True)
        socket_path = f.name
        f.close()

        proc = subprocess.Popen(["sudo", "-n", "-u", "mytardis",
                                 "_datafiledescriptord",
                                 mytardis_install_dir, auth_provider,
                                 socket_path, str(experiment_id),
                                 str(datafile_id)],
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE)

        while not os.path.exists(socket_path):
            time.sleep(0.01)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        sock.send("Request file descriptor")
        (message, file_descriptors) = fdsend.recvfds(sock, 128, numfds=1)
        sock.close()

        file_descriptor = None
        if len(file_descriptors) > 0:
            file_descriptor = file_descriptors[0]

        return MyTardisDatafileDescriptor(message, file_descriptor)

if __name__ == "__main__":
    experiment_id = "2151"
    print "Experiment ID: " + experiment_id
    datafile_id = "14751"
    print "Datafile ID: " + datafile_id

    mytardis_datafile_descriptor = \
        MyTardisDatafileDescriptor.get_file_descriptor("/opt/mytardis/develop",
                                                       "ldap",
                                                       experiment_id,
                                                       datafile_id)
    if mytardis_datafile_descriptor.file_descriptor is not None:
        print "Message: " + mytardis_datafile_descriptor.message

        file_descriptor = mytardis_datafile_descriptor.file_descriptor
        file_handle = os.fdopen(file_descriptor, 'rb')

        # Only show first 1024 bytes for now:
        print "File content: " + file_handle.read(1024)
        file_handle.close()
    else:
        print "mytardis_datafile_descriptor.file_descriptor is None."
