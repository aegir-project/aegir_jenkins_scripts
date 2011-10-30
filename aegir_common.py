#! /usr/bin/env python

"""Common functions for the Aegir tesing scripts
"""

import fabric.api as fabric
import os, sys

class Usage(Exception):
        def __init__(self, msg):
                self.msg = msg

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

def run_provision_tests():
        print "===> Running Provision tests"
        fabric.run("su - -s /bin/sh aegir -c '/var/aegir/drush/drush.php @hostmaster provision-tests-run -y'", pty=True)

        # Fabric command to fetch Provision
def fab_fetch_provision(release_type, aegir_version):
        if release_type == "git":
                print "===> Fetching Provision - via git"
                fabric.run("su - -s /bin/sh aegir -c 'mkdir ~/.drush'", pty=True)
                fabric.run("su - -s /bin/sh aegir -c 'git clone http://git.drupal.org/project/provision.git ~/.drush/provision'", pty=True)
                fabric.run("su - -s /bin/sh aegir -c 'cd ~/.drush/provision && git checkout %s'" % (aegir_version), pty=True)
        else:
                print "===> Fetching Provision - via package"
                fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php dl -y --destination=/var/aegir/.drush provision-%s'" % (aegir_version), pty=True)

# Fabric command to run the install.sh aegir script
def fab_hostmaster_install(domain, email, mysqlpass):
        print "===> Running hostmaster-install"
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php hostmaster-install %s --client_email=%s --aegir_db_pass=%s --yes'" % (domain, email, mysqlpass), pty=True)
        fabric.run("su - -s /bin/sh aegir -c 'php /var/aegir/drush/drush.php -y @hostmaster vset hosting_queue_tasks_frequency 1'", pty=True)
        fab_run_dispatch()
