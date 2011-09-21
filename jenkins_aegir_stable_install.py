#! /usr/bin/env python

import aegir_stable_install
import os, sys



if __name__ == "__main__":
    args = [
        'dummy',
        "--aegir_version=" + os.environ['AEGIR_VERSION'] + "",
        "--release_type=" + os.environ['AEGIR_FETCH_MODE'] + "",
        "--drush_version=" + os.environ['DRUSH_VERSION'] + "",
    ]

    sys.exit(aegir_stable_install.main(args))

