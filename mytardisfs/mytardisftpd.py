import sys
import os
import subprocess
import time


def run():
    HOME = os.getenv("HOME")

    proc = subprocess.Popen(["stat", "-f", "-c", "%T",
                             os.path.join(HOME, "MyTardis")],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    stdout, stderr = proc.communicate()
    filesystem_type = stdout.strip()
    if filesystem_type == "fuseblk":
        # Avoid STDOUT if run from /usr/local/lib/openssh/sftp-server
        if sys.stdout.isatty():
            print ""
            print "ERROR: " + \
                "You already have a FUSE filesystem mounted on ~/MyTardis"
            print ""
            print "You can unmount MyTardis by running:"
            print ""
            print "    fusermount -uz ~/MyTardis"
            print ""
        sys.exit(1)

    stdout_log_filename = os.path.join(HOME, "mytardisftpd.log")
    stderr_log_filename = os.path.join(HOME, "mytardisftpd-error.log")

    mytardisfs_proc = None

    with open(stdout_log_filename, 'w') as out, \
            open(stderr_log_filename, 'w') as err:
        mytardisfs_proc = \
            subprocess.Popen(["mytardisfs",
                              os.path.join(HOME, "MyTardis"),
                              "-f", "-o", "direct_io"],
                             stdout=out, stderr=err)

    if mytardisfs_proc is None:
        print ""
        print "ERROR: mytardisfs failed to start."
        print ""
        print "Perhaps there was a problem with writing to ~/mytardisftpd.log"
        print "or to ~/mytardisftpd-error.log ?"
        print ""

    count = 0
    while count < 100:
        mytardisfs_proc.poll()
        if mytardisfs_proc.returncode is not None \
                and mytardisfs_proc.returncode != 0:
            break

        proc = subprocess.Popen(["stat", "-f", "-c", "%T",
                                 os.path.join(HOME, "MyTardis")],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        stdout, stderr = proc.communicate()
        filesystem_type = stdout.strip()
        if filesystem_type == "fuseblk":
            # Avoid STDOUT if run from /usr/local/lib/openssh/sftp-server
            if sys.stdout.isatty():
                print ""
                print "Your MyTardis data has been mounted at ~/MyTardis/"
                print "You can unmount MyTardis by running:"
                print ""
                print "    fusermount -uz ~/MyTardis"
                print ""
            sys.exit(0)
        time.sleep(0.1)
        count = count + 1

    print ""
    if count == 100:
        print os.path.join(HOME, "MyTardis") + \
            " still isn't mounted after 10 seconds."
    else:
        print os.path.join(HOME, "MyTardis") + \
            " failed to mount."
    print ""
    print "You could look in: "
    print ""
    print "    ~/mytardisftpd-error.log"
    print ""
    print "If you don't spot any errors, you can continue to check ~/MyTardis "
    print "and check for a \"mytardisfs\" process running under your account."
    print ""
    print "If you want to terminate the \"mytardisfs\" process and unmount"
    print "~/MyTardis, then you can do so by running:"
    print ""
    print "    fusermount -uz ~/MyTardis"
    print ""

    sys.exit(1)
