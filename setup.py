from setuptools import setup

setup(name='mytardisfs',
      version='0.1',
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
      zip_safe=False)
