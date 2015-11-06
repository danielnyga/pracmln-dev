FROM ubuntu:trusty

# a few minor docker-specific tweaks
# see https://github.com/docker/docker/blob/master/contrib/mkimage/debootstrap
#RUN echo '#!/bin/sh' > /usr/sbin/policy-rc.d \
#	&& echo 'exit 101' >> /usr/sbin/policy-rc.d \
#	&& chmod +x /usr/sbin/policy-rc.d \
#	\
#	&& dpkg-divert --local --rename --add /sbin/initctl \
#	&& cp -a /usr/sbin/policy-rc.d /sbin/initctl \
#	&& sed -i 's/^exit.*/exit 0/' /sbin/initctl \
#	\
#	&& echo 'force-unsafe-io' > /etc/dpkg/dpkg.cfg.d/docker-apt-speedup \
#	\
#	&& echo 'DPkg::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' > /etc/apt/apt.conf.d/docker-clean \
#	&& echo 'APT::Update::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' >> /etc/apt/apt.conf.d/docker-clean \
#	&& echo 'Dir::Cache::pkgcache ""; Dir::Cache::srcpkgcache "";' >> /etc/apt/apt.conf.d/docker-clean \
#	\
#	&& echo 'Acquire::Languages "none";' > /etc/apt/apt.conf.d/docker-no-languages \
#	\
#	&& echo 'Acquire::GzipIndexes "true"; Acquire::CompressionTypes::Order:: "gz";' > /etc/apt/apt.conf.d/docker-gzip-indexes

# enable the universe
RUN sed -i 's/^#\s*\(deb.*universe\)$/\1/g' /etc/apt/sources.list
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y -q bash build-essential gfortran libatlas-base-dev libffi-dev libssl-dev git python2.7 python2.7-dev python-pip python-setuptools python-tk python-scipy
RUN rm /bin/sh && ln -s /bin/bash /bin/sh 
ADD requirements.txt /requirements.txt
RUN sudo pip install --upgrade pip && sudo pip install -U -r /requirements.txt
#RUN sudo pip install --upgrade numpy && sudo pip install scipy 

# RUN git clone https://github.com/danielnyga/pracmln

RUN mkdir pracmln
ADD src pracmln
RUN cd pracmln  && python setup.py --docs && chmod +x env.sh && . ./env.sh && echo PYTHONPATH: && echo $PYTHONPATH && python test.py

# overwrite this with 'CMD []' in a dependent Dockerfile
CMD ["/bin/bash"]
#ENTRYPOINT /bin/bash /