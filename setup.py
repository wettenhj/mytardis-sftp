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
              "_datafiledescriptord = mytardisfs.datafiledescriptord:run",
              "mytardisfs = mytardisfs.mytardisfs:run",
              "mytardisftpd = mytardisfs.mytardisftpd:run",
          ],
      },
      install_requires=['fuse-python', 'python-dateutil', 'requests',
                        'fdsend'],
      zip_safe=False)

if 'install' in sys.argv:
    man_path = '/usr/share/man/man1/'
    if os.path.exists(man_path):
        print("Installing man page for mytardisfs...")
        man_page = "doc/mytardisfs.1"
        shutil.copy2(man_page, man_path)
        os.chmod(man_path + 'mytardisfs.1', int('444', 8))
