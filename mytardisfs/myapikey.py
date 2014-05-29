#!/usr/bin/python

# Filename: myapikey.py
# Author: James Wettenhall <james.wettenhall@monash.edu>
# Description: Used by mytardisfs to obtain a user's API key.

import sys
import os
import getpass


def run():
    # This script should be run as user 'mytardis' via sudo.
    # All users have permission to run it as sudo without a password,
    # thanks to this line in /etc/sudoers:
    # ALL     ALL=(ALL) NOPASSWD: /usr/local/bin/_myapikey,
    #    /usr/local/bin/_datafiledescriptord, /usr/local/bin/_datasetdatafiles

    if getpass.getuser() != "mytardis" or "SUDO_USER" not in os.environ:
        print "Usage: sudo -u mytardis _myapikey"
        os._exit(1)

    sys.path.append("/opt/mytardis/current/")
    for egg in os.listdir("/opt/mytardis/current/eggs/"):
        sys.path.append("/opt/mytardis/current/eggs/" + egg)
    from django.core.management import setup_environ
    from tardis import settings
    setup_environ(settings)

    from tardis.tardis_portal.models import UserAuthentication
    from tastypie.models import ApiKey

    userAuth = UserAuthentication.objects \
        .get(username=os.environ['SUDO_USER'],
             authenticationMethod='cvl_ldap')
    myTardisUser = userAuth.userProfile.user

    key = ApiKey.objects.get(user__username=myTardisUser.username)
    print "ApiKey " + myTardisUser.username + ":" + str(key.key)
