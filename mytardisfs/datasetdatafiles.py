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


def run():
    if getpass.getuser() != "mytardis" or "SUDO_USER" not in os.environ:
        print "Usage: sudo -u mytardis _datasetdatafiles EXP_ID DATASET_ID"
        sys.exit(1)

    if len(sys.argv) < 3:
        print "Usage: sudo -u mytardis _datasetdatafiles EXP_ID DATASET_ID"
        sys.exit(1)

    sys.path.append("/opt/mytardis/current/")
    for egg in os.listdir("/opt/mytardis/current/eggs/"):
        sys.path.append("/opt/mytardis/current/eggs/" + egg)
    from django.core.management import setup_environ
    from tardis import settings
    setup_environ(settings)

    from tardis.tardis_portal.models import Dataset, Dataset_File, Experiment
    from tardis.tardis_portal.models import UserAuthentication
    from django.core.exceptions import ObjectDoesNotExist

    experiment_id = int(sys.argv[1])
    dataset_id = int(sys.argv[2])

    found_user = False
    mytardis_user = None
    exp_public = False
    exp_owned_or_shared = False
    staff_or_superuser = False
    found_dataset_in_experiment = False
    try:
        userAuth = UserAuthentication.objects \
            .get(username=os.environ['SUDO_USER'],
                 authenticationMethod='cvl_ldap')
        mytardis_user = userAuth.userProfile.user
        # logger.debug("Primary MyTardis username: " + mytardis_user.username)
        # print "Primary MyTardis username: " + mytardis_user.username
        found_user = True
        staff_or_superuser = mytardis_user.is_staff or \
            mytardis_user.is_superuser
        if not staff_or_superuser:
            exp = Experiment.objects.get(id=experiment_id)
            exp_public = Experiment \
                .public_access_implies_distribution(exp.public_access)
            exps_owned_and_shared = Experiment.safe \
                .owned_and_shared(mytardis_user)
            exp_owned_or_shared = exps_owned_and_shared \
                .filter(id=experiment_id).exists()
            for dataset in exp.datasets.all():
                if dataset.id == dataset_id:
                    found_dataset_in_experiment = True
                    break
        if staff_or_superuser or (found_dataset_in_experiment and
                                  (exp_public or exp_owned_or_shared)):
            dfs = Dataset_File.objects.filter(dataset__id=dataset_id)
            df_list = []
            for df in dfs:
                df_fields = dict(id=df.id, directory=df.directory,
                                 created_time=str(df.created_time),
                                 modification_time=str(df.modification_time),
                                filename=df.filename, size=df.size)
                df_list.append(df_fields)
            print str(df_list)
        elif not found_dataset_in_experiment:
            print "Data set (ID %s) does not belong to experiment (ID %s)." % \
                (str(dataset_id), str(experiment_id))
        else:
            print "Access to data set %s denied for user %s." % \
                (str(dataset_id), os.environ['SUDO_USER'])
    except ObjectDoesNotExist:
        print traceback.format_exc()
        # print "User " + os.environ['SUDO_USER'] + " \
        #    was not found in MyTardis."
    except:
        print traceback.format_exc()
