FROM joeyh/debian-stable-amd64

ENV http_proxy = http://192.168.130.73:3128
ENV https_proxy = https://192.168.130.73:3128

RUN sed -i 's/ftp.us.debian.org/ftp.nl.debian.org/g' /etc/apt/sources.list
RUN apt-get update
RUN apt-get install --yes devscripts build-essential debian-keyring
#ENTRYPOINT ["sdk"]

RUN apt-get install --yes git-core git-buildpackage

VOLUME ["/data"]

RUN cd /root; git clone https://github.com/aegir-project/aegir_jenkins_scripts.git

RUN cd /root; git clone --branch 7.x-3.x git://git.drupalcode.org/project/provision || git pull



RUN cd /root/provision; ../aegir_jenkins_scripts/jenkins-debian-build -k jenkins@ci.aegirproject.org -u

