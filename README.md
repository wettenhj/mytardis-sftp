mytardis-sftp
=============
The scripts in this repository form an early prototype for making MyTardis data available via SFTP (and related methods such as RSYNC over SSH), using Python-Fuse.  These scripts currently sit in /usr/local/bin/ on my MyTardis server.  The main script is mytardis\_mount, which uses Python-Fuse to set up a virtual filesystem.  The mytardis\_sftpd script is an easy way to call mytardis\_mount - it automatically chooses a mountpoint, ~/MyTardis, calls mytardis\_mount, and waits for the FUSE filesystem to be ready, returning 0 on success, and 1 if it's not ready after 5 seconds.  

Launching mytardis-sftp (a Python-Fuse process).
-----------------------------------------------
At present, the scripts are designed to be run by an ordinary user (whose POSIX username from LDAP matches their MyTardis username).  For interactive SSH login, mytardis\_sftpd can be run automatically by placing it in /etc/profile.  For SFTP login, /etc/ssh/sshd\_config can be modified to point to a custom sftp-subsystem script, e.g. /usr/local/lib/openssh/sftp-server, instead of the default /usr/lib/openssh/sftp-server executable, and this custom script can start up mytardis\_sftpd before running /usr/local/lib/sftp-server.  For RSYNC over SSH, you can use --rsync-path="/usr/local/bin/mytardis\_sftpd && /usr/bin/rsync" to ensure that mytardis-sftp is available for the rsync.

LDAP
----
This method of providing SFTP access depends on using an LDAP directory for authentication in MyTardis and configuring PAM and NSS to allow SSH/SFTP logins, using LDAP credentials.  This code has been run on Ubuntu 12.04.2 (Precise).  PAM and NSS were configured for LDAP, using these instructions: http://askubuntu.com/questions/127389/how-to-configure-ubuntu-as-an-ldap-client .  This means that the same credentials can be used to log into the MyTardis web interface and into the SFTP server.  

How the Python-Fuse process accesses MyTardis
---------------------------------------------
There are two different ways in which mytardis-sftp accesses MyTardis:

1. Using MyTardis's TastyPie RESTful API
2. Using Django (with some "sudo -u mytardis" trickery)

The API was the preferred method in early discussions with stakeholders, however it is not clear that we can get reasonable performance out of the API for serving up files via SFTP from a virtual FUSE filesystem.  The problem is that SFTP clients expect large files to begin downloading immediately (in small chunks), so they can update their progress dialogs.  The API doesn't have an efficient way to serve up a series of small chunks, and if the Python-Fuse process waits for the entire datafile to be served up by the API before making it available to the SFTP server, then the SFTP client can get confused and think that the connection to the SFTP server has stopped responding. 

The other method is to use Django to access the MyTardis data.  For example, the script af\_unix\_socket\_server is designed to be run with "sudo -u mytardis", so that it can access the MyTardis file store directly, open a data file, and hand the file descriptor over to the unprivileged mytardis\_mount process.  The af\_unix\_socket\_server script checks the SUDO\_USER environment variable to determine the POSIX username calling the script, which is assumed to be the same as the MyTardis username.  To be more accurate, a MyTardis user can link multiple authentication methods e.g. username "jsmith" (using LDAP) and username "johns" (using localdb).  So if the af\_unix\_socket\_server receives SUDO\_USER=jsmith, it looks up username="jsmith" in MyTardis's UserAuthentication model with auth\_method="cvl\_ldap".  Of course the auth\_method should be easily configurable, but it is hard-coded for now.

To allow regular users to run scripts like af\_unix\_socket\_server, we need to add a rule into /etc/sudoers.  *BE CAREFUL EDITING THIS FILE - USE visudo OR sudoedit TO ENSURE THAT YOU DON'T ACCIDENTALLY CREATE A SYNTAX ERROR WHICH COMPLETELY DISABLES YOUR SUDO ACCESS.*  Rules in /etc/sudoers are read in order from top to bottom, so if you add a 
rule down the bottom, then you can be sure that it won't be overwritten by any subsequent rules.
```
ALL     ALL=(mytardis:mytardis) NOPASSWD: /usr/local/bin/my_api_key, /usr/local/bin/af_unix_socket_server, /usr/local/bin/get_dataset_datafiles
```

If you're wondering why we have an arbitrary looking "get\_dataset\_datafiles" script (which as the name suggests, queries MyTardis for a list of datafiles belonging to a given dataset), it is because most queries like this are currently done with the TastyPie RESTful API.  But just recently, I have been testing whether it is actually faster to do these queries using the Django models instead.

*WARNING: THE "sudo -u mytardis" METHOD OF ALLOWING UNPRIVILEGED USERS TO ACCESS PARTS OF MyTardis IS UNCONVENTIONAL AND MAY HAVE UNINTENDED CONSEQUENCES, e.g. a huge /var/log/auth.log FILE.  THIS METHOD IS BEING TRIALED, BUT IT MAY PROVE TO BE UNSUITABLE FOR SOME (OR ALL) MyTardis DEPLOYMENTS.*
