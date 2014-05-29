#!/usr/bin/python

# A client process, running as a regular LDAP username (matching a MyTardis
# username) runs this script, which runs as user "mytardis", via 
# "sudo -u mytardis", thanks to a rule within /etc/sudoers.

# This script can determine the username which the client script is 
# running as, thanks to the SUDO_USER environment variable, so it will 
# only provide access to experiment IDs available to that MyTardis
# username.  Currently the username is matched using the "cvl_ldap"
# authentication scheme in our MyTardis deployment 
# (defined in /opt/mytardis/current/tardis/settings.py)

# If the user (os.environ['SUDO_USER']) is a MyTardis superuser,
# then we don't bother checking whether the requested dataset ID
# belongs to the supplied experiment ID, because they will have
# access to that dataset no matter what.

import os
import sys
import getpass
import traceback

if getpass.getuser()!="mytardis" or "SUDO_USER" not in os.environ:
    print "Usage: sudo -u mytardis get_dataset_datafiles EXP_ID DATASET_ID"
    sys.exit(1)

if len(sys.argv)<3:
    print "Usage: sudo -u mytardis get_dataset_datafiles EXP_ID DATASET_ID"
    sys.exit(1)

experimentId = int(sys.argv[1])
datasetId = int(sys.argv[2])

sys.path.append("/opt/mytardis/current/")
for egg in os.listdir("/opt/mytardis/current/eggs/"):
    sys.path.append("/opt/mytardis/current/eggs/" + egg)
from django.core.management import setup_environ
from django.core.exceptions import ObjectDoesNotExist
from tardis import settings
setup_environ(settings)

from tardis.tardis_portal.models import Dataset, Dataset_File, Experiment
from tardis.tardis_portal.models import UserAuthentication

foundUser = False
myTardisUser = None
expPublic = False
expOwnedOrShared = False
staffOrSuperuser = False
foundDatasetInExperiment = False
try:
    userAuth = UserAuthentication.objects.get(username=os.environ['SUDO_USER'], \
        authenticationMethod='cvl_ldap')
    myTardisUser = userAuth.userProfile.user
    #logger.debug("Primary MyTardis username: " + myTardisUser.username)
    #print "Primary MyTardis username: " + myTardisUser.username
    foundUser = True
    staffOrSuperuser = myTardisUser.is_staff or myTardisUser.is_superuser
    if not staffOrSuperuser:
        exp = Experiment.objects.get(id=experimentId)
        expPublic = Experiment.public_access_implies_distribution(exp.public_access)
        experimentsOwnedAndShared = Experiment.safe.owned_and_shared(myTardisUser)
        expOwnedOrShared = experimentsOwnedAndShared.filter(id=experimentId).exists()
        for dataset in exp.datasets.all():
            if dataset.id==datasetId:
                foundDatasetInExperiment = True
                break
    if staffOrSuperuser or (foundDatasetInExperiment and (expPublic or expOwnedOrShared)):
        dfs = Dataset_File.objects.filter(dataset__id=datasetId)
        dfList = []
        for df in dfs:
            dfFields = dict(id=df.id, directory=df.directory, filename=df.filename, size=df.size)
            dfList.append(dfFields)
        print str(dfList)
    elif not foundDatasetInExperiment:
        print "Datafile (ID %s) does not belong to experiment (ID %s)." % (str(datasetId), str(experimentId))
    else:
        print "Access to datafile %s denied for user %s." % (str(datasetId),os.environ['SUDO_USER'])
except ObjectDoesNotExist:
    print traceback.format_exc()
    #print "User " + os.environ['SUDO_USER'] + " was not found in MyTardis."
except:
    print traceback.format_exc()

