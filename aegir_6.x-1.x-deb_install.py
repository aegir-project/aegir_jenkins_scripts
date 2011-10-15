#! /usr/bin/env python

from libcloud.types import Provider
from libcloud.providers import get_driver
from libcloud.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.ssh import SSHClient, ParamikoSSHClient
import libcloud.security
import os, sys, string, ConfigParser, socket
import fabric.api as fabric
import time

libcloud.security.VERIFY_SSL_CERT = True


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
        fabric.run("for source in 95.142.164.178 59.167.182.161 174.136.104.138 217.155.126.38; do iptables -I INPUT -s $source -p tcp --dport 22 -j ACCEPT; iptables -I INPUT -s $source -p tcp --dport 80 -j ACCEPT; done; iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT; iptables --policy INPUT DROP", pty=True)

# Fabric command to add the apt sources
def fab_add_apt_sources():
        print "===> Adding apt sources"
        # Add the apt-key for Koumbit.
        fabric.run("curl http://debian.aegirproject.org/key.asc | apt-key add -", pty=True)
        # Add the unstable Koumbit repositories, these should contain the dev version of Aegir.
        fabric.run("echo 'deb http://debian.aegirproject.org unstable main' >> /etc/apt/sources.list", pty=True)
        # Add the squeeze-backports repo for Drush.
        fabric.run("echo 'deb http://backports.debian.org/debian-backports squeeze-backports main' >> /etc/apt/sources.list", pty=True)
        # Pin to using the version of Drush from squeeze-backports, so we use a 'stable' version.
        fabric.run("echo 'Package: drush' >> /etc/apt/preferences", pty=True)
        fabric.run("echo 'Pin: release a=squeeze-backports' >> /etc/apt/preferences", pty=True)
        fabric.run("echo 'Pin-Priority: 1001' >> /etc/apt/preferences", pty=True)
        fabric.run("apt-get update", pty=True)

# Fabric command to install Aegir using apt_get
def fab_install_aegir(domain, email, mysqlpass):
        print "===> Installing Aegir"
        # Preseed the options for the aegir package.
        fabric.run("apt-get install debconf-utils -y", pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/db_password password %s' | debconf-set-selections" % (mysqlpass), pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/db_password seen true' | debconf-set-selections", pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/db_host string localhost' | debconf-set-selections", pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/email string %s' | debconf-set-selections" % (email), pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/site string %s' | debconf-set-selections" % (domain), pty=True)
        fabric.run("echo 'aegir-hostmaster aegir/makefile string http://drupalcode.org/project/provision.git/blob_plain/6.x-1.x:/aegir.make' | debconf-set-selections", pty=True)
        # Install aegir, but ensure that no questions are prompted.
        fabric.run("DPKG_DEBUG=developer DEBIAN_FRONTEND=noninteractive apt-get install aegir -y", pty=True)


# Fabric command to add the aegir user to sudoers
# We need to do this manually, because the package doesn't support our old version of debian.
def fab_prepare_user():
        print "===> Preparing the Aegir user"
        fabric.run("echo 'aegir ALL=NOPASSWD: /usr/sbin/apache2ctl' >> /etc/sudoers", pty=True)

# Fabric command to set up the hosting queue
def fab_hostmaster_setup():
        print "===> Setup hosting queue frequency"
        fabric.run("su - -s /bin/sh aegir -c 'drush -y @hostmaster vset hosting_queue_tasks_frequency 1'", pty=True)
        fab_run_dispatch()

# Download, import and verify platforms
def fab_install_platform(platform_name):
        fabric.run("su - -s /bin/sh aegir -c 'drush make https://github.com/mig5/builds/raw/master/%s.build /var/aegir/platforms/%s'" % (platform_name, platform_name), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'drush --root=\'/var/aegir/platforms/%s\' provision-save \'@platform_%s\' --context_type=\'platform\''" % (platform_name, platform_name), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'drush @hostmaster hosting-import \'@platform_%s\''" % platform_name, pty=True)
        fab_run_dispatch()

# Install a site
def fab_install_site(platform_name, profile):
        fabric.run("su - -s /bin/sh aegir -c 'drush --uri=\'%s.mig5.net\' provision-save \'@%s.mig5.net\' --context_type=\'site\' --platform=\'@platform_%s\' --profile=\'%s\' --db_server=\'@server_localhost\''" % (platform_name, platform_name, platform_name, profile), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'drush @%s.mig5.net provision-install'" % platform_name, pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'drush @hostmaster hosting-task @platform_%s verify'" % platform_name, pty=True)
        fab_run_dispatch()

# Force the dispatcher
def fab_run_dispatch():
        fabric.run("su - -s /bin/sh aegir -c 'drush @hostmaster hosting-dispatch'", pty=True)

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

# Remove and purge the aegir debian install
def fab_uninstall_aegir():
        fabric.run("apt-get remove --purge aegir aegir-hostmaster aegir-provision drush -y", pty=True)


def main():
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
                fab_prepare_user()
                fab_add_apt_sources()
                fab_install_aegir(domain, email, mysqlpass)
                fab_hostmaster_setup()
                run_platform_tests()
                run_site_tests()
                fab_uninstall_aegir()
        except:
                print "===> Test failure"
                raise
        finally:
                print "===> Destroying this node"
                conn.destroy_node(node)

        return 0

if __name__ == "__main__":
        main()
