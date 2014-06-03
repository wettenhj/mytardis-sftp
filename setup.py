from setuptools import setup
import sys
import os
import shutil

import mytardisfs

setup(name='mytardisfs',
      version=mytardisfs.__version__,
      description='FUSE filesystem for MyTardis',
      url='http://github.com/monash-merc/mytardisfs',
      author='James Wettenhall',
      author_email='james.wettenhall@monash.edu',
      license='GPL',
      packages=['mytardisfs'],
      entry_points={
          "console_scripts": [
              "_myapikey = mytardisfs.myapikey:run",
              "_datasetdatafiles = mytardisfs.datasetdatafiles:run",
              "_countexpdatasets = mytardisfs.countexpdatasets:run",
              "_datafiledescriptord = mytardisfs.datafiledescriptord:run",
              "mytardisfs = mytardisfs.mytardisfs:run",
              "mytardisftpd = mytardisfs.mytardisftpd:run",
          ],
      },
      #install_requires=['fuse-python==0.2.1', 'python-dateutil', 'requests',
                        #'fdsend', 'ConfigParser'],
      install_requires=['python-dateutil', 'requests',
                        'fdsend', 'ConfigParser'],
      zip_safe=False)

if 'install' in sys.argv:
    print ""
    man_path = '/usr/share/man/man1/'
    if os.path.exists(man_path):
        print "Installing /usr/share/man/man1/mytardisfs.1"
        man_page = "doc/mytardisfs.1"
        shutil.copy2(man_page, man_path)
        os.chmod(man_path + 'mytardisfs.1', int('444', 8))
    config_path = '/etc/'
    if os.path.exists(config_path):
        config_filename = "mytardisfs.cnf"
        config_src_file = os.path.join("etc", config_filename)
        config_file_path = os.path.join("/etc", config_filename)
        if os.path.exists(config_file_path):
            print "Not overwriting existing " + config_file_path
        else:
            print "Installing /etc/mytardisfs.cnf"
            shutil.copy2(config_src_file, config_path)
            os.chmod(config_file_path, int('644', 8))
    print ""
    print "WARNING: The fuse-python package is not included in setup.py's\n" + \
        "install_requires, because installing it automatically from PyPI\n" + \
        "currently gives version 0.2-pre3, whereas MyTardisFS works best\n" + \
        "with fuse-python 0.2.1, which can be installed on Ubuntu 12.04 with:\n\n" + \
        "    sudo apt-get install python-fuse"
    print ""
