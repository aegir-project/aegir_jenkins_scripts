#! /usr/bin/env python

import aegir_non_package_upgrade
import os, sys



if __name__ == "__main__":
    args = [
        'dummy',
        "--aegir_version=" + os.environ['AEGIR_VERSION'] + "",
        "--drush_version=" + os.environ['DRUSH_VERSION'] + "",
        "--upgrade_version=" + os.environ['UPGRADE_VERSION'] + "",
        "--test_type=" + os.environ['TEST_TYPE'] + "",
    ]

    sys.exit(aegir_non_package_upgrade.main(args))

