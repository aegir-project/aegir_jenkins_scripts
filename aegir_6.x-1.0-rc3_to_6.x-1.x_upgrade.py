#! /usr/bin/env python

from libcloud.types import Provider
from libcloud.providers import get_driver
from libcloud.deployment import MultiStepDeployment, ScriptDeployment, SSHKeyDeployment
from libcloud.ssh import SSHClient, ParamikoSSHClient
import os, sys, string, ConfigParser, socket
import fabric.api as fabric
import time

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
def fab_fetch_drush():
        print "===> Fetching Drush"
        fabric.run("su - -s /bin/sh aegir -c 'wget http://ftp.drupal.org/files/projects/drush-7.x-4.4.tar.gz'", pty=True)
        fabric.run("su - -s /bin/sh aegir -c' gunzip -c drush-7.x-4.4.tar.gz | tar -xf - '", pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'rm /var/aegir/drush-7.x-4.4.tar.gz'", pty=True)

# Fabric command to fetch Provision
def fab_fetch_provision():
        print "===> Fetching Provision"
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php -y dl provision-6.x-1.0-rc3'", pty=True)

# Fabric command to run the install.sh aegir script
def fab_hostmaster_install(domain, email, mysqlpass):
        print "===> Running hostmaster-install"
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php hostmaster-install %s --client_email=%s --aegir_db_pass=%s --yes'" % (domain, email, mysqlpass), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php -y @hostmaster vset hosting_queue_tasks_frequency 1'", pty=True)
        fab_run_dispatch()

# Force the dispatcher
def fab_run_dispatch():
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php @hostmaster hosting-dispatch'", pty=True)

# Fabric command to fetch the upgrade.sh aegir script
def fab_fetch_upgrade_script():
        print "===> Fetching the Aegir upgrade script"
        fabric.run("wget -O /tmp/upgrade.sh 'http://drupalcode.org/project/provision.git/blob_plain/HEAD:/upgrade.sh.txt'", pty=True)

# Fabric command to run the upgrade.sh aegir script
def fab_run_upgrade_script(domain):
        print "===> Running the Aegir upgrade script"
        fabric.run("su - -s /bin/sh aegir -c 'yes | sh /tmp/upgrade.sh %s'" % domain, pty=True)
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
        fabric.run("su - -s /bin/sh aegir -c '/var/aegir/drush/drush.php @hostmaster hosting-task @platform_%s verify'" % platform_name, pty=True)
        fab_run_dispatch()


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
                fab_prepare_apache()
                fab_prepare_user()
                fab_fetch_drush()
                fab_fetch_provision()
                fab_hostmaster_install(domain, email, mysqlpass)
                fab_fetch_upgrade_script()
                fab_run_upgrade_script(domain)
                run_platform_tests()
                run_site_tests()
        except:
                e = sys.exc.info()[1]
                raise SystemError(e)

        print "===> Destroying this node"
        conn.destroy_node(node)


if __name__ == "__main__":
        main()
