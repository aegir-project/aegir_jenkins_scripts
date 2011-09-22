#! /usr/bin/env python

import aegir_dev_install
import os, sys



if __name__ == "__main__":
    args = [
        'dummy',
        "--aegir_version=" + os.environ['AEGIR_VERSION'] + "",
        "--drush_version=" + os.environ['DRUSH_VERSION'] + "",
    ]

    sys.exit(aegir_dev_install.main(args))

