FROM joeyh/debian-stable-amd64

RUN apt-get update
RUN apt-get install --yes devscripts build-essential debian-keyring dh-systemd

RUN apt-get install --yes git-core git-buildpackage

RUN cd /root; git clone --branch 7.x-3.x https://github.com/aegir-project/aegir_jenkins_scripts.git
VOLUME ["/root/aegir_jenkins_scripts"]

RUN cd /root; git clone --branch 7.x-3.x git://git.drupalcode.org/project/provision
VOLUME ["/root/provision"]

# the place where we drop the build packages.
VOLUME ["/incoming"]
COPY .dput.cf /root/

VOLUME ["/root/.gnupg"]

# Build.
CMD cd /root/provision; ../aegir_jenkins_scripts/jenkins-debian-build -k jenkins@ci.aegirproject.org -u

