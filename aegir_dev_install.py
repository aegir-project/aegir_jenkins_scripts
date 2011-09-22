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
import os, sys, string, ConfigParser, socket, getopt
import fabric.api as fabric
import time

class Usage(Exception):
        def __init__(self, msg):
                self.msg = msg

# Fetch some values from the config file
config = ConfigParser.RawConfigParser()
config.read(os.path.expanduser("~/frigg.ini"))

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

# Some basic dependency tests for this job itself
def dependency_check():
        try:   
                open(os.path.expanduser("~/.ssh/id_rsa.pub")).read()
        except IOError:
                print "You need at least a public key called id_rsa.pub in your .ssh directory"
                sys.exit(1)
        try:   
                import fabric                                   

        except ImportError:
                print "You need Fabric installed (apt-get install fabric)"
                sys.exit(1)

# Prepare a basic firewall
def fab_prepare_firewall():
        print "===> Setting a little firewall"
        fabric.run("for source in 95.142.164.178 59.167.182.161 174.136.104.138; do iptables -I INPUT -s $source -p tcp --dport 22 -j ACCEPT; iptables -I INPUT -s $source -p tcp --dport 80 -j ACCEPT; done; iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT; iptables --policy INPUT DROP", pty=True)

# Fabric command to set some Apache requirements
def fab_prepare_apache():
        print "===> Preparing Apache"
        fabric.run("a2enmod rewrite", pty=True)
        fabric.run("ln -s /var/aegir/config/apache.conf /etc/apache2/conf.d/aegir.conf", pty=True)

# Fabric command to add the aegir user and to sudoers also
def fab_prepare_user():
        print "===> Preparing the Aegir user"
        fabric.run("useradd -r -U -d /var/aegir -m -G www-data aegir", pty=True)
        fabric.run("echo 'aegir ALL=NOPASSWD: /usr/sbin/apache2ctl' >> /etc/sudoers", pty=True)

# Fabric command to fetch Drush
def fab_fetch_drush(drush_version):
        print "===> Fetching Drush %s" % (drush_version)
        fabric.run("su - -s /bin/sh aegir -c 'wget http://ftp.drupal.org/files/projects/drush-%s.tar.gz'" % (drush_version), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'gunzip -c drush-%s.tar.gz | tar -xf - '" % (drush_version), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'rm /var/aegir/drush-%s.tar.gz'" % (drush_version), pty=True)

# Fabric command to fetch Provision
def fab_fetch_provision(aegir_version):
        print "===> Fetching Provision - via git"
        fabric.run("su - -s /bin/sh aegir -c 'mkdir ~/.drush'", pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'git clone --branch %s http://git.drupal.org/project/provision.git ~/.drush/provision'" % (aegir_version), pty=True)
        

# Fabric command to run the install.sh aegir script
def fab_hostmaster_install(domain, email, mysqlpass):
        print "===> Running hostmaster-install"
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php hostmaster-install %s --client_email=%s --aegir_db_pass=%s --yes'" % (domain, email, mysqlpass), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php -y @hostmaster vset hosting_queue_tasks_frequency 1'", pty=True)
        fab_run_dispatch()

# Download, import and verify platforms
def fab_install_platform(platform_name):
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php make https://github.com/mig5/builds/raw/master/%s.build /var/aegir/platforms/%s'" % (platform_name, platform_name), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php --root=\'/var/aegir/platforms/%s\' provision-save \'@platform_%s\' --context_type=\'platform\''" % (platform_name, platform_name), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php @hostmaster hosting-import \'@platform_%s\''" % platform_name, pty=True)
        fab_run_dispatch()

# Install a site
def fab_install_site(platform_name, profile):
        fabric.run("su - -s /bin/sh aegir -c '/var/aegir/drush/drush.php --uri=\'%s.mig5.net\' provision-save \'@%s.mig5.net\' --context_type=\'site\' --platform=\'@platform_%s\' --profile=\'%s\' --db_server=\'@server_localhost\''" % (platform_name, platform_name, platform_name, profile), pty=True)
        fabric.run("su - -s /bin/sh aegir -c '/var/aegir/drush/drush.php @%s.mig5.net provision-install'" % platform_name, pty=True)
        fabric.run("su - -s /bin/sh aegir -c '/var/aegir/drush/drush.php @hostmaster hosting-task --force @platform_%s verify'" % platform_name, pty=True)
        fab_run_dispatch()

# Force the dispatcher
def fab_run_dispatch():
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php @hostmaster hosting-dispatch'", pty=True)

def run_platform_tests():
        print "===> Installing some common platforms"
        fab_install_platform('drupal6')
        fab_install_platform('drupal7')
        fab_install_platform('openatrium')

def run_site_tests():
        print "===> Installing some sites"
        fab_install_site('drupal6', 'default')
        fab_install_site('drupal7', 'standard')
        fab_install_site('openatrium', 'openatrium')

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
                                return 0;
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
                        fab_fetch_provision(aegir_version)
                        fab_hostmaster_install(domain, email, mysqlpass)
                        run_platform_tests()
                        run_site_tests()
                except:
                        e = sys.exc.info()[1]
                        raise SystemError(e)
        
                print "===> Destroying this node"
                conn.destroy_node(node)
                
                return 0
        
        except Usage, err:
                print >>sys.stderr, err.msg
                print >>sys.stderr, "for help use --help"
                return 2

if __name__ == "__main__":
        sys.exit(main())
