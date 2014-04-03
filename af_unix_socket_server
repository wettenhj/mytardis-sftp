#!/usr/bin/python

# Socket server program which opens file with elevated privileges, and then
# passes file descriptor to another Python process via an IPC socket.

# A client process, running as a regular LDAP username (matching a MyTardis
# username) starts this server process, which, (running as user "mytardis", 
# via "sudo -u mytardis", thanks to a rule within /etc/sudoers), has 
# read-access to all datafiles. This server process can determine the username 
# which the client script is running as, thanks to the SUDO_USER environment
# variable, so it will only provide access to experiment IDs available to 
# that MyTardis username.  Currently the username is matched using the 
# "cvl_ldap" authentication scheme in our MyTardis deployment 
# (defined in /opt/mytardis/current/tardis/settings.py)

import socket,os
import fdsend
import sys
import getpass
import traceback

if getpass.getuser()!="mytardis" or "SUDO_USER" not in os.environ:
    print "Usage: sudo -u mytardis af_unix_socket_server SOCKET_PATH EXP_ID DATAFILE_ID"
    sys.exit(1)

if len(sys.argv)<4:
    print "Usage: sudo -u mytardis af_unix_socket_server SOCKET_PATH EXP_ID DATAFILE_ID"
    sys.exit(1)

socketPath = sys.argv[1]
experimentId = int(sys.argv[2])
datafileId = int(sys.argv[3])

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    os.remove(socketPath)
except OSError:
    pass
sock.bind(socketPath)
os.chmod(socketPath, 0666)
sock.listen(1)
conn, addr = sock.accept()

sys.path.append("/opt/mytardis/current/")
for egg in os.listdir("/opt/mytardis/current/eggs/"):
    sys.path.append("/opt/mytardis/current/eggs/" + egg)
from django.core.management import setup_environ
from django.core.exceptions import ObjectDoesNotExist
from tardis import settings
setup_environ(settings)

from tardis.tardis_portal.models import Dataset_File, Experiment
from tardis.tardis_portal.models import UserAuthentication

foundUser = False
myTardisUser = None
expPublic = False
expOwnedOrShared = False
staffOrSuperuser = False
foundDatafileInExperiment = False
try:
    userAuth = UserAuthentication.objects.get(username=os.environ['SUDO_USER'], \
        authenticationMethod='cvl_ldap')
    myTardisUser = userAuth.userProfile.user
    #logger.debug("Primary MyTardis username: " + myTardisUser.username)
    foundUser = True
    staffOrSuperuser = myTardisUser.is_staff or myTardisUser.is_superuser
    if not staffOrSuperuser:
        exp = Experiment.objects.get(id=experimentId)
        expPublic = Experiment.public_access_implies_distribution(exp.public_access)
        experimentsOwnedAndShared = Experiment.safe.owned_and_shared(myTardisUser)
        expOwnedOrShared = experimentsOwnedAndShared.filter(id=experimentId).exists()
        for df in exp.get_datafiles():
            if df.id==datafileId:
                foundDatafileInExperiment = True
                break
    df = Dataset_File.objects.get(id=datafileId)
    r = df.get_preferred_replica()
    filepath = r.get_absolute_filepath()

    # The following line blocks, waiting for client to start up and send its request:
    file_descriptor_request = conn.recv(1024)
    if staffOrSuperuser or (foundDatafileInExperiment and (expPublic or expOwnedOrShared)):
        fds = [ file(filepath, 'rb') ]
        message = "Success"
    elif not foundDatafileInExperiment:
        fds = []
        message = "Datafile (ID %s) does not belong to experiment (ID %s)." % (str(datafileId), str(experimentId))
    else:
        fds = []
        #message = "Access to datafile %s denied for user %s." % (str(datafileId),os.environ['SUDO_USER'])
        message = "Access denied for user " + os.environ['SUDO_USER'] + " " + str(sys.argv)
    fdsend.sendfds(conn, message, fds = fds)
except ObjectDoesNotExist:
    message = "User " + os.environ['SUDO_USER'] + " was not found in MyTardis."
    fdsend.sendfds(conn, message, fds = [])
except:
    message = traceback.format_exc()
    fdsend.sendfds(conn, message, fds = [])

conn.close()

try:
    os.remove(socketPath)
except OSError:
    pass
