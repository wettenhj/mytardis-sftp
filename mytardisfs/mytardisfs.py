#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Based on Steve Androulakis's
# proof of concept that produces a virtual FUSE-mountable
# file/directory structure from a python dictionary
# By Steve Androulakis <http://github.com/steveandroulakis>
# Requires FUSE (linux: use package manager to install)
# Requires python-fuse: pip install fuse-python
# Requires dateutil:    pip install python-dateutil
# Requires requests:    pip install requests
# USE:
# mkdir MyTardis
# Mount: mytardisfs MyTardis -f
# Unmount: fusermount -uz MyTardis

# To Do: Make sure file/directory names are legal, e.g. they shouldn't
# contain the '/' character. Grischa suggests replacing '/' with '-'.

# To Do: Improve efficiency / response time, e.g. re-use locally cached
# query results for list of experiments, list of datasets or list of
# datafiles if the previous query was less than n seconds ago (e.g. n=30).
# Already done for list of experiments.  We don't cache datafile content.

# To Do: Make sure directories are refreshed when necessary,
# e.g. when a new dataset is added.

# To Do: Tidy up code and make it PEP-8 compliant.

# To Do: Implement nlink for experiment directories.  Already done for
# root directory and for dataset directories.

# To Do: Implement datafile timestamps for stat.

# To Do: Remove hard-coding of things like "cvl_ldap" - the MyTardis
# authentication method used to resolve the POSIX username and obtain
# the API key.  This should probably be a command-line argument of
# mtardisfs.

# To Do: The following need to be accessible as a command-line options:
# EXPERIMENTS_LIST_CACHE_TIME_SECONDS = 30
# _mytardis_url = "https://mytardis.massive.org.au"
# The latter is only used for RESTful API calls.  Currently, other code
# in MyTardisFS requires it to run on the MyTardis server.
# Also the MyTardis installation dir (e.g. /opt/mytardis/current)
# and the use_api option for datafiles.

import fuse
import stat
import time
import requests
import os
import sys
import getpass
import subprocess
import logging
import traceback
import threading
import ast
import errno
from datafiledescriptor import MyTardisDatafileDescriptor
import dateutil.parser
from datetime import datetime
import getopt
from __init__ import __version__

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# We don't really want to log to STDOUT.  We assume that this script
# will be called with STDOUT redirected to a file.
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
log_format_string = \
    '%(asctime)s - %(name)s - %(module)s - %(funcName)s - ' + \
    '%(lineno)d - %(levelname)s - %(message)s'
stream_handler.setFormatter(logging.Formatter(log_format_string))
logger.addHandler(stream_handler)

if len(sys.argv) < 2:
    print "Missing mount point"
    print "See `mytardisfs -h' for usage"
    sys.exit(1)

if sys.argv[1].startswith("-"):
    argv = sys.argv[1:]
else:
    argv = sys.argv[2:]

try:
    opts, args = getopt.getopt(argv, "hvfdsl:o:",
                               ["help", "version", "loglevel="])
except getopt.GetoptError:
    print "Usage: mytardisfs mountpoint [options]"
    sys.exit(1)

for opt, arg in opts:
    if opt == '-h' or opt == '--help':
        print ""
        print "Usage: mytardisfs mountpoint [options]"
        print "  e.g. mytardisfs ~/MyTardis -f -o direct_io"
        print """
General options:
    -h   --help            print help
    -v   --version         print version

MyTardisFS options:
    -l   --loglevel=LEVEL  set log level to ERROR, WARNING, INFO or DEBUG

FUSE options:
    -d   -o debug          enable debug output (implies -f)
    -f                     foreground operation
    -s                     disable multi-threaded operation

    -o allow_other         allow access to other users
    -o allow_root          allow access to root
    -o nonempty            allow mounts over non-empty file/dir
    -o default_permissions enable permission checking by kernel
    -o fsname=NAME         set filesystem name
    -o subtype=NAME        set filesystem type
    -o large_read          issue large read requests (2.4 only)
    -o max_read=N          set maximum size of read requests

    -o hard_remove         immediate removal (don't hide files)
    -o use_ino             let filesystem set inode numbers
    -o readdir_ino         try to fill in d_ino in readdir
    -o direct_io           use direct I/O
    -o kernel_cache        cache files in kernel
    -o [no]auto_cache      enable caching based on modification times (off)
    -o umask=M             set file permissions (octal)
    -o uid=N               set file owner
    -o gid=N               set file group
    -o entry_timeout=T     cache timeout for names (1.0s)
    -o negative_timeout=T  cache timeout for deleted names (0.0s)
    -o attr_timeout=T      cache timeout for attributes (1.0s)
    -o ac_attr_timeout=T   auto cache timeout for attributes (attr_timeout)
    -o intr                allow requests to be interrupted
    -o intr_signal=NUM     signal to send on interrupt (10)
    -o modules=M1[:M2...]  names of modules to push onto filesystem stack

    -o max_write=N         set maximum size of write requests
    -o max_readahead=N     set maximum readahead
    -o async_read          perform reads asynchronously (default)
    -o sync_read           perform reads synchronously
    -o atomic_o_trunc      enable atomic open+truncate support
    -o big_writes          enable larger than 4kB writes
    -o no_remote_lock      disable remote file locking
"""

        sys.exit()
    if opt == '-v' or opt == '--version':
        print ""
        print "MyTardisFS version: " + __version__
        print "fuse-python version: " + fuse.__version__
        print "FUSE version: " + \
            subprocess.check_output('ldconfig -v 2>/dev/null | grep fuse',
                                    shell=True)
        sys.exit()
    if opt == '-l' or opt == '--loglevel':
        # Remove this option from sys.argv,
        # because it is not a valid FUSE
        # option, and all command-line options
        # will be passed to FUSE.
        try:
            sys.argv.remove(opt + "=" + arg)
        except:
            try:
                sys.argv.remove(opt + arg)
            except:
                try:
                    sys.argv.remove(opt)
                    sys.argv.remove(arg)
                except:
                    pass
        if arg == 'ERROR':
            logger.setLevel(logging.ERROR)
            stream_handler.setLevel(logging.ERROR)
        elif arg == 'WARNING':
            logger.setLevel(logging.WARNING)
            stream_handler.setLevel(logging.WARNING)
        elif arg == 'INFO':
            logger.setLevel(logging.INFO)
            stream_handler.setLevel(logging.INFO)
        elif arg == 'DEBUG':
            logger.setLevel(logging.DEBUG)
            stream_handler.setLevel(logging.DEBUG)
            # FUSE needs to run in foreground mode (-f) to allow
            # debug-level logging.  You can still use an ampersand
            # at the end of the command to put it in the background.
            # The logs can be redirected to files, as done in mytardisftpd
            if '-f' not in sys.argv:
                sys.argv.append('-f')
        else:
            print "--loglevel should be ERROR, WARNING, INFO or DEBUG."
            sys.exit(1)

# Checking again, after possible removing "--loglevel"
if len(sys.argv) < 2:
    print "Missing mount point"
    print "See `mytardisfs -h' for usage"
    sys.exit(1)

fuse_mount_dir = os.path.expanduser(sys.argv[1])
if not os.path.exists(fuse_mount_dir):
    os.makedirs(fuse_mount_dir)

mytardis_username = getpass.getuser()
proc = subprocess.Popen(["sudo", "-u", "mytardis", "_myapikey"],
                        stdout=subprocess.PIPE)
myapikey_stdout = proc.stdout.read().strip()
mytardis_username = myapikey_stdout.split(' ')[1].split(':')[0]
mytardis_apikey = myapikey_stdout.split(':')[-1]

proc = subprocess.Popen(["id", "-u"], stdout=subprocess.PIPE)
_uid = proc.stdout.read().strip()

proc = subprocess.Popen(["id", "-g"], stdout=subprocess.PIPE)
_gid = proc.stdout.read().strip()

_mytardis_url = "https://mytardis.massive.org.au"
_headers = {'Authorization': 'ApiKey ' + mytardis_username + ":" +
            mytardis_apikey}

_directory_size = 4096

EXPERIMENTS_LIST_CACHE_TIME_SECONDS = 30
LAST_QUERY_TIME = dict()
LAST_QUERY_TIME['experiments'] = datetime.fromtimestamp(0)

fuse.fuse_python_api = (0, 2)

# Timestamps obtained from MyTardis queries will be used
# if available.
# Start-up time of this FUSE process is the default
# timestamp for everything:
_file_default_timestamp = int(time.time())

# FILES[directory/file/path] = (size_in_bytes, is_directory)
# FILES[directory/file/path] = (size_in_bytes, is_directory,
#     accessed, modified, created, nlink)
FILES = dict()
DATAFILE_IDS = dict()
DATAFILE_SIZES = dict()
DATAFILE_FILE_OBJECTS = dict()
DATAFILE_CLOSE_TIMERS = dict()

url = _mytardis_url + "/api/v1/experiment/?format=json&limit=0"
logger.info(url)
response = requests.get(url=url, headers=_headers)
exp_records_json = response.json()
num_exp_records_found = exp_records_json['meta']['total_count']
logger.info(str(num_exp_records_found) +
            " experiment record(s) found for user " + mytardis_username)
if int(num_exp_records_found) > 0:
    max_exp_created_time = \
        dateutil.parser.parse(exp_records_json['objects'][0]['created_time'])
for exp_record_json in exp_records_json['objects']:
    exp_dir_name = str(exp_record_json['id']) + "-" + \
        exp_record_json['title'].encode('ascii', 'ignore').replace(" ", "_")
    exp_created_time = dateutil.parser.parse(exp_record_json['created_time'])
    if exp_created_time > max_exp_created_time:
        max_exp_created_time = exp_created_time
    FILES['/' + exp_dir_name] = \
        (0, True,
         int(time.mktime(exp_created_time.timetuple())),
         int(time.mktime(exp_created_time.timetuple())),
         int(time.mktime(exp_created_time.timetuple())))
    # logger.info("FILES['/'" + exp_dir_name + "] = " +
    #     str(FILES['/' + exp_dir_name]))

# Add 2 to nlink for "." and ".."
FILES['/'] = (0, True,
              int(time.mktime(max_exp_created_time.timetuple())),
              int(time.mktime(max_exp_created_time.timetuple())),
              int(time.mktime(max_exp_created_time.timetuple())),
              int(num_exp_records_found)+2)
# logger.info("FILES['/'] = " + str(FILES['/']))

LAST_QUERY_TIME['experiments'] = datetime.now()


def file_array_to_list(files):
    # Files need to be returned in this format:
    # FILES = [('file1', 15, False), ('file2', 15, False),
    #          ('directory', 15, True)]

    l = list()
    for key, val in files.iteritems():
        l.append((file_from_key(key), val[0], val[1]))

    return l


def file_from_key(key):
    return key.rsplit(os.sep)[-1]


class MyStat(fuse.Stat):
    """
    Convenient class for Stat objects.
    Set up the stat object with appropriate
    values depending on constructor args.
    """
    def __init__(self, is_dir, size,
                 accessed=_file_default_timestamp,
                 modified=_file_default_timestamp,
                 created=_file_default_timestamp,
                 nlink=0):
        fuse.Stat.__init__(self)
        if is_dir:
            self.st_mode = stat.S_IFDIR | stat.S_IRUSR | stat.S_IXUSR
            if nlink != 0:
                self.st_nlink = nlink
            else:
                # A directory without subdirectories
                # still has "." and ".."
                self.st_nlink = 2
            self.st_size = _directory_size
        else:
            self.st_mode = stat.S_IFREG | stat.S_IRUSR
            self.st_nlink = 1
            self.st_size = size
        self.st_atime = accessed
        self.st_mtime = modified
        self.st_ctime = created

        self.st_uid = int(_uid)
        self.st_gid = int(_gid)


class MyFS(fuse.Fuse):
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

    def getattr(self, path):
        path = path.rstrip("*")
        if path != "/":
            path = path.rstrip("/")
        logger.debug("^ getattr: path = " + path)

        # if path == "." or path == "..":
        #     return MyStat(True, _directory_size)
        if path == "/":
            if len(FILES[path]) >= 6:
                return MyStat(True, _directory_size,
                              FILES[path][2], FILES[path][3], FILES[path][4],
                              FILES[path][5])
            else:
                return MyStat(True, _directory_size)
        else:
            try:
                if len(FILES[path]) >= 5:
                    return MyStat(FILES[path][1], FILES[path][0],
                                  FILES[path][2], FILES[path][3],
                                  FILES[path][4])
                else:
                    return MyStat(FILES[path][1], FILES[path][0])
            except KeyError:
                return -errno.ENOENT

    def getdir(self, path):
        logger.debug('getdir called:', path)
        return file_array_to_list(FILES)

    def readdir(self, path, offset):
        logger.debug("^ readdir: path = \"" + path + "\"")

        for e in '.', '..':
            yield fuse.Direntry(e)

        pathComponents = path.split(os.sep, 3)
        if pathComponents == ['', '']:
            pathComponents = ['']
        if len(pathComponents) > 1 and pathComponents[1] != '':
            exp_dir_name = pathComponents[1]
            experiment_id = exp_dir_name.split("-")[0]
        if len(pathComponents) > 2 and pathComponents[2] != '':
            dataset_dir_name = pathComponents[2]
            dataset_id = dataset_dir_name.split("-")[0]
        # subdirectory is not used in "def readdir". Should it be?
        if len(pathComponents) > 3 and pathComponents[3] != '':
            subdirectory = pathComponents[3]

        if len(pathComponents) == 1:
            time_since_last_experiment_query = datetime.now() - \
                LAST_QUERY_TIME['experiments']
            if time_since_last_experiment_query.seconds > \
                    EXPERIMENTS_LIST_CACHE_TIME_SECONDS:
                url = _mytardis_url + "/api/v1/experiment/?format=json&limit=0"
                logger.info(url)
                response = requests.get(url=url, headers=_headers)
                if response.status_code < 200 or response.status_code >= 300:
                    logger.info(url)
                    logger.info("Response status_code = " +
                                str(response.status_code))
                exp_records_json = response.json()
                num_exp_records_found = exp_records_json['meta']['total_count']
                logger.info(str(num_exp_records_found) +
                            " experiment record(s) found for user " +
                            mytardis_username)

                # Doesn't check for deleted experiments,
                # only adds to FILES dictionary.
                if int(num_exp_records_found) > 0:
                    max_exp_created_time = dateutil.parser \
                        .parse(exp_records_json['objects'][0]['created_time'])
                for exp_record_json in exp_records_json['objects']:
                    exp_dir_name = str(exp_record_json['id']) + "-" + \
                        (exp_record_json['title'].encode('ascii', 'ignore')
                            .replace(" ", "_"))
                    exp_created_time = \
                        dateutil.parser.parse(exp_record_json['created_time'])
                    if exp_created_time > max_exp_created_time:
                        max_exp_created_time = exp_created_time
                    FILES['/' + exp_dir_name] = \
                        (0, True,
                         int(time.mktime(exp_created_time.timetuple())),
                         int(time.mktime(exp_created_time.timetuple())),
                         int(time.mktime(exp_created_time.timetuple())))
                FILES['/'] = \
                    (0, True,
                     int(time.mktime(max_exp_created_time.timetuple())),
                     int(time.mktime(max_exp_created_time.timetuple())),
                     int(time.mktime(max_exp_created_time.timetuple())),
                     # Add 2 to nlink for "." and ".."
                     int(num_exp_records_found) + 2)
                LAST_QUERY_TIME['experiments'] = datetime.now()

        if len(pathComponents) == 2 and pathComponents[1] != '':
            url = _mytardis_url + \
                "/api/v1/dataset/?format=json&limit=0&experiments__id=" + \
                experiment_id
            logger.info(url)
            response = requests.get(url=url, headers=_headers)
            if response.status_code < 200 or response.status_code >= 300:
                logger.info("Response status_code = " +
                            str(response.status_code))
            dataset_records_json = response.json()
            num_dataset_records_found = \
                dataset_records_json['meta']['total_count']
            logger.info(str(num_dataset_records_found) +
                        " dataset record(s) found for exp ID " +
                        experiment_id)

            for dataset_json in dataset_records_json['objects']:
                dataset_dir_name = str(dataset_json['id']) + "-" + \
                    (dataset_json['description'].encode('ascii', 'ignore')
                        .replace(" ", "_"))
                FILES['/' + exp_dir_name + '/' + dataset_dir_name] = (0, True)

        if len(pathComponents) == 3 and pathComponents[1] != '':
            FILES['/' + exp_dir_name + '/' + dataset_dir_name] = (0, True)
            DATAFILE_IDS[dataset_id] = dict()
            DATAFILE_SIZES[dataset_id] = dict()
            DATAFILE_FILE_OBJECTS[dataset_id] = dict()
            DATAFILE_CLOSE_TIMERS[dataset_id] = dict()

            use_api = False

            if use_api:
                url = _mytardis_url + \
                    "/api/v1/dataset_file/?format=json&limit=0&" + \
                    "dataset__id=" + str(dataset_id)
                logger.info(url)
                response = requests.get(url=url, headers=_headers)
                datafile_records_json = response.json()
                num_datafile_records_found = \
                    datafile_records_json['meta']['total_count']
            else:
                cmd = ['sudo', '-u', 'mytardis',
                       '/usr/local/bin/_datasetdatafiles',
                       experiment_id, dataset_id]
                logger.info(str(cmd))
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                stdout, stderr = proc.communicate()
                if stderr is not None and stderr != "":
                    logger.info(stderr)

                datafile_dicts_string = stdout.strip()
                # logger.info("datafile_dicts_string: " +
                #     datafile_dicts_string)
                datafile_dicts = ast.literal_eval(datafile_dicts_string)
                num_datafile_records_found = len(datafile_dicts)

            logger.info(str(num_datafile_records_found) +
                        " datafile record(s) found for dataset ID " +
                        str(dataset_id))

            if use_api:
                datafile_dicts = datafile_records_json['objects']

            for df in datafile_dicts:
                # logger.debug("df = " + str(df))
                datafile_id = df['id']
                if use_api:
                    datafile_directory = df['directory'] \
                        .encode('ascii', 'ignore').strip('/')
                else:
                    datafile_directory = df['directory']
                    if datafile_directory is None:
                        datafile_directory = ""
                    else:
                        datafile_directory = datafile_directory \
                            .encode('ascii', 'ignore').strip('/')
                datafile_name = df['filename'] \
                    .encode('ascii', 'ignore')
                datafile_size = int(df['size'].encode('ascii', 'ignore'))
                try:
                    datafile_created_time_datetime = \
                        dateutil.parser.parse(df['created_time'])
                    datafile_created_timetuple = \
                        datafile_created_time_datetime.timetuple()
                    datafile_created_time = \
                        int(time.mktime(datafile_created_timetuple))
                except:
                    logger.debug(traceback.format_exc())
                    datafile_created_time = _file_default_timestamp
                try:
                    datafile_modification_time_datetime = \
                        dateutil.parser.parse(df['modification_time'])
                    datafile_modification_timetuple = \
                        datafile_modification_time_datetime.timetuple()
                    datafile_modification_time = \
                        int(time.mktime(datafile_modification_timetuple))
                except:
                    logger.debug(traceback.format_exc())
                    datafile_modification_time = _file_default_timestamp

                datafile_accessed_time = datafile_modification_time

                if datafile_directory != "":
                    # Intermediate subdirectories
                    for i in reversed(range(1,
                                      len(datafile_directory.split('/')))):
                        intermediate_subdirectory = \
                            datafile_directory.rsplit('/', i)[0]
                        FILES['/' + exp_dir_name + '/' + dataset_dir_name +
                              '/' + intermediate_subdirectory] = \
                            (0, True,
                             datafile_accessed_time,
                             datafile_modification_time,
                             datafile_created_time)

                    FILES['/' + exp_dir_name + '/' + dataset_dir_name + '/' +
                          datafile_directory] = \
                        (0, True,
                         datafile_accessed_time,
                         datafile_modification_time,
                         datafile_created_time)
                    FILES['/' + exp_dir_name + '/' + dataset_dir_name + '/' +
                          datafile_directory + '/' + datafile_name] \
                        = (datafile_size, False,
                           datafile_accessed_time,
                           datafile_modification_time,
                           datafile_created_time)
                else:
                    FILES['/' + exp_dir_name + '/' + dataset_dir_name + '/' +
                          datafile_name] = (datafile_size, False,
                                            datafile_accessed_time,
                                            datafile_modification_time,
                                            datafile_created_time)
                if datafile_directory not in DATAFILE_IDS[dataset_id]:
                    DATAFILE_IDS[dataset_id][datafile_directory] = dict()
                DATAFILE_IDS[dataset_id][datafile_directory][datafile_name] \
                    = datafile_id
                if datafile_directory not in DATAFILE_SIZES[dataset_id]:
                    DATAFILE_SIZES[dataset_id][datafile_directory] = dict()
                DATAFILE_SIZES[dataset_id][datafile_directory][datafile_name] \
                    = datafile_size
                if datafile_directory not in DATAFILE_FILE_OBJECTS[dataset_id]:
                    DATAFILE_FILE_OBJECTS[dataset_id][datafile_directory] \
                        = dict()
                dfodict = DATAFILE_FILE_OBJECTS[dataset_id][datafile_directory]
                dfodict[datafile_name] = None
                if datafile_directory not in DATAFILE_CLOSE_TIMERS[dataset_id]:
                    DATAFILE_CLOSE_TIMERS[dataset_id][datafile_directory] \
                        = dict()
                dctdict = DATAFILE_CLOSE_TIMERS[dataset_id][datafile_directory]
                dctdict[datafile_name] = None

        path_depth = path.count('/')
        # FIXME: Iterating through the entire FILES dictionary is inefficient
        for key, val in FILES.iteritems():
            if key == "/":
                continue

            key_depth = key.count('/')

            if path == "/":
                path_depth = 0

            if key.startswith(path) and key_depth == path_depth + 1:
                yield(fuse.Direntry(file_from_key(key)))

    def read(self, path, leng, offset):

        logger.debug("read(...) path = " + path)

        filename = path.rsplit(os.sep)[-1]
        pathComponents = path.split(os.sep, 3)
        if pathComponents == ['', '']:
            pathComponents = ['']
        experiment_id = pathComponents[1].split("-")[0]
        dataset_id = pathComponents[2].split("-")[0]
        if os.sep in pathComponents[3]:
            subdirectory = pathComponents[3].rsplit(os.sep, 1)[0]
        else:
            subdirectory = ""
        logger.debug("read request for %s with length %d and offset %d" %
                     (filename, leng, offset))

        datafile_id = DATAFILE_IDS[dataset_id][subdirectory][filename]

        datafile_size = DATAFILE_SIZES[dataset_id][subdirectory][filename]
        logger.debug("datafile_size is " + str(datafile_size))

        if DATAFILE_FILE_OBJECTS[dataset_id][subdirectory][filename] \
                is not None:
            # Found a file object to reuse,
            # so let's reset the timer for closing the file:
            file_object = \
                DATAFILE_FILE_OBJECTS[dataset_id][subdirectory][filename]
            DATAFILE_CLOSE_TIMERS[dataset_id][subdirectory][filename].cancel()

            def closeFile(fileObj, dictObj, key):
                fileObj.close()
                dictObj[key] = None

            dfodict = DATAFILE_FILE_OBJECTS[dataset_id][subdirectory]
            DATAFILE_CLOSE_TIMERS[dataset_id][subdirectory][filename] \
                = threading.Timer(30.0, closeFile, [file_object, dfodict,
                                                    filename])
            DATAFILE_CLOSE_TIMERS[dataset_id][subdirectory][filename].start()
        else:
            mytardis_datafile_descriptor = MyTardisDatafileDescriptor. \
                get_file_descriptor(experiment_id, datafile_id)
            file_descriptor = None
            logger.debug("Message: " +
                         mytardis_datafile_descriptor.message)
            if mytardis_datafile_descriptor.file_descriptor is not None:
                file_descriptor = mytardis_datafile_descriptor.file_descriptor
            else:
                logger.info("mytardis_datafile_descriptor.file_descriptor "
                            "is None.")

            file_object = os.fdopen(file_descriptor)
            DATAFILE_FILE_OBJECTS[dataset_id][subdirectory][filename] = \
                file_object

            # Schedule file to be closed in 30 seconds, unless it is used
            # before then, in which case the timer will be reset.

            def closeFile(fileObj, dictObj, key):
                fileObj.close()
                dictObj[key] = None

            dfodict = DATAFILE_FILE_OBJECTS[dataset_id][subdirectory]
            DATAFILE_CLOSE_TIMERS[dataset_id][subdirectory][filename] = \
                threading.Timer(30.0, closeFile, [file_object, dfodict,
                                                  filename])
            DATAFILE_CLOSE_TIMERS[dataset_id][subdirectory][filename].start()

        file_object.seek(offset)
        data = file_object.read(leng)

        return data

if __name__ == '__main__':
    fs = MyFS()
    fs.parse(errex=1)
    fs.main()


def run():
    fs = MyFS()
    fs.parse(errex=1)
    fs.main()
