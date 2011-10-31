#! /usr/bin/env python

"""Aegir dev branch testing script

Valid options:
--aegir_version - The branch of aegir to test (required)
--drush_version - The version of Drush to use in the testing (required)
--help - Print this help
"""

from libcloud.types import Provider
from libcloud.providers import get_driver
from libcloud.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.ssh import SSHClient, ParamikoSSHClient
from aegir_common import Usage, dependency_check, fab_prepare_firewall, fab_prepare_apache, fab_prepare_user, fab_fetch_drush, fab_run_dispatch, run_provision_tests, fab_fetch_provision, fab_hostmaster_install
import os, sys, string, ConfigParser, socket, getopt
import fabric.api as fabric
import time

# Fetch some values from the config file
config = ConfigParser.RawConfigParser()
config.read(os.path.expanduser("~/frigg-php-5.2.ini"))

# Try to abstract the provider here, as we may end up supporting others
# Theoretically since we are using libcloud, it should support any
# provider that supports the deploy_node function (Amazon EC2 doesn't)
provider = config.get('Aegir', 'provider')
provider_driver = config.get(provider, 'driver')

# API credentials
user = config.get(provider, 'user')
key = config.get(provider, 'key')

# Preferred image and size
config_distro = config.get(provider, 'distro')
config_size = config.get(provider, 'size')

# These are used as options to Aegir during install
email = config.get('Aegir', 'email')
        

def main(argv=None):
        if argv is None:
                argv = sys.argv
        try:
                try:
                        opts, args = getopt.getopt(argv[1:], "h", ["help", "aegir_version=", "drush_version="])
                except getopt.error, msg:
                        raise Usage(msg)
                # process options
                aegir_version = None
                drush_version = None
                for o, a in opts:
                        if o in ("-h", "--help"):
                                print __doc__
                                return 0
                        if o in ("--aegir_version"):
                                aegir_version = a
                        if o in ("--drush_version"):
                                drush_version = a                                
                
                # Check the command line options
                if aegir_version is None:
                        raise Usage, "the --aegir_version option must be specified"
                if drush_version is None:
                        raise Usage, "the --drush_version option must be specified"
                
                
                # Now we can get on with the testing
        
                # Run some tests
                dependency_check()
        
                # Make a new connection
                Driver = get_driver( getattr(Provider, provider_driver) )
                conn = Driver(user, key)
        
                # Get a list of the available images and sizes
                images = conn.list_images()
                sizes = conn.list_sizes()
        
                # We'll use the distro and size from the config ini
                preferred_image = [image for image in images if config_distro in image.name]
                assert len(preferred_image) == 1, "We found more than one image for %s, will be assuming the first one" % config_distro
        
                preferred_size = [size for size in sizes if config_size in size.name]
        
                # The MySQL root password is hardcoded here for now, as it's in our Squeeze LAMP image.
                mysqlpass = "8su43x"
        
                # Commands to run immediately after installation
                dispatch = [
                        SSHKeyDeployment(open(os.path.expanduser("~/.ssh/id_rsa.pub")).read()),
                ]
                msd = MultiStepDeployment(dispatch)
        
                # Create and deploy a new server now, and run the deployment steps defined above
                print "Provisioning server and running deployment processes"
                try:
                        node = conn.deploy_node(name='aegir' + os.environ['BUILD_ID'], image=preferred_image[0], size=preferred_size[0], deploy=msd)                                             
                except:
                        e = sys.exc_info()[1]
                        raise SystemError(e)
        
                print "Provisioning complete, you can ssh as root to %s" % node.public_ip[0]
                if node.extra.get('password'):
                        print "The root user's password is %s" % node.extra.get('password')
        
                # Setting some parameters for fabric
                domain = socket.getfqdn(node.public_ip[0])
                fabric.env.host_string = domain
                fabric.env.user = 'root'
        
                try:
                        fab_prepare_firewall()
                        fab_prepare_apache()
                        fab_prepare_user()
                        fab_fetch_drush(drush_version)
                        fab_fetch_provision('git', aegir_version)
                        fab_hostmaster_install(domain, email, mysqlpass)
                        run_provision_tests()
                except:
                        print "===> Test failure"
                        raise
                finally: 
                        print "===> Destroying this node"
                        conn.destroy_node(node)
                
                return 0
        
        except Usage, err:
                print >>sys.stderr, err.msg
                print >>sys.stderr, "for help use --help"
                return 2

if __name__ == "__main__":
        sys.exit(main())
