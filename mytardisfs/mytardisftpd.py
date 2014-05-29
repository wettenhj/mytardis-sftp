
import sys
import os
import subprocess
import time

def run():
    HOME = os.getenv("HOME")
    stdout_log_filename = os.path.join(HOME, "mytardisftpd.log")
    stderr_log_filename = os.path.join(HOME, "mytardisftpd-error.log")

    with open(stdout_log_filename, 'w') as out, \
            open(stderr_log_filename, 'w') as err:
        subprocess.Popen(["mytardisfs",
                         os.path.join(HOME, "MyTardis"),
                         "-f", "-o", "direct_io"],
                        stdout=out, stderr=err)

    count = 0
    while count < 50:
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

    print os.path.join(HOME, "MyTardis") + " failed to mount after 5 seconds."
    print "You could try: "
    print "  tail $HOME/mytardisftpd-error.log"
    print "  tail $HOME/mytardisftpd.log"

    sys.exit(1)
