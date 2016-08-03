#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import stat
import sys
import platform
import shutil
import imp

sys.path.append(os.path.join(os.getcwd(), 'pracmln'))
sys.path.append(os.path.join(os.getcwd(), '3rdparty', 'logutils-0.3.3'))

from pracmln.mln.util import colorize

packages = [('numpy', 'numpy', False),
            ('tabulate', 'tabulate', False),
            ('pyparsing', 'pyparsing', False),
            ('psutil', 'psutil', False),
            ('matplotlib', 'matplotlib', False),
            ('networkx', 'networkx', False)]

docspackages = [('sphinx', 'sphinx sphinxcontrib-bibtex', False)]

python_apps = [
    {"name": "mlnquery", "script": "$PRACMLN_HOME/pracmln/mlnquery.py"},
    {"name": "mlnlearn", "script": "$PRACMLN_HOME/pracmln/mlnlearn.py"},
    {"name": "xval", "script": "$PRACMLN_HOME/pracmln/xval.py"}
]


def check_package(pkg):
    try:
        sys.stdout.write('checking dependency %s...' % pkg[0])
        imp.find_module(pkg[0])
        sys.stdout.write(colorize('OK', (None, 'green', True), True))
        print
    except ImportError:
        print
        print colorize('%s was not found. Please install by '
                       '"sudo pip install %s" %s' % (pkg[0],
                                                     pkg[1],
                                                     '(optional)' if pkg[2] else ''),
                       (None, 'yellow', True), True)


# check the package dependecies
def check_dependencies():
    for pkg in packages:
        check_package(pkg)
    print


def adapt(name, arch):
    return name.replace("<ARCH>", arch)\
               .replace("$PRACMLN_HOME", os.path.abspath("."))\
               .replace("/", os.path.sep)


def buildLibpracmln():
    envsetup = 'export LD_LIBRARY_PATH="{0}/lib:${{LD_LIBRARY_PATH}}"\n'
    envsetup += 'export LIBRARY_PATH="{0}/lib:${{LIBRARY_PATH}}"\n'
    envsetup += 'export CPATH="{0}/include:${{CPATH}}"\n'
    envsetup += 'export CMAKE_LIBRARY_PATH="{0}/lib:${{CMAKE_LIBRARY_PATH}}"\n'
    envsetup += 'export CMAKE_INCLUDE_PATH="{0}/include:${{CMAKE_INCLUDE_PATH}}"\n'

    oldwd = os.getcwd()
    basepath = os.path.join(os.getcwd(), 'libpracmln')
    buildpath = os.path.join(basepath, 'build')
    installpath = os.path.join(basepath, 'install')

    if os.path.exists(buildpath):
        shutil.rmtree(buildpath, True)
    if os.path.exists(installpath):
        shutil.rmtree(installpath, True)

    os.mkdir(buildpath)
    os.chdir(buildpath)

    ret = os.system("cmake ..")
    if ret != 0:
        os.chdir(oldwd)
        return None

    ret = os.system("make")
    if ret != 0:
        os.chdir(oldwd)
        return None

    ret = os.system("make install")
    if ret != 0:
        os.chdir(oldwd)
        return None

    os.chdir(oldwd)

    return envsetup.format(installpath)


def build_docs():
    print colorize('Building documentation', (None, 'green', True), True)
    for pkg in docspackages:
        check_package(pkg)
    print
    docs = adapt("cd $PRACMLN_HOME/doc && make html && cd -", arch)
    os.system(docs)


def test():
    print colorize('Checking docker...', (None, None, True), True),
    try:
        import docker
        print colorize('OK', (None, 'green', True), True)
    except ImportError:
        print colorize('Docker is not installed. '
                       'To install, conduct the following actions:',
                       (None, 'red', True), True),
        print '  wget https://get.docker.com/ | sh'
        print '  sudo groupadd docker'
        print '  sudo gpasswd -a $USER docker'
        print '  sudo service docker restart'
        print '  newgrp'
        print 
        print '  # test docker'
        print '  docker run hello-world'
        print 
        print '  # install python bindings'
        print '  sudo pip install docker-py'
        exit(-1)

    from docker import Client
    c = Client(base_url='unix://var/run/docker.sock')
    print colorize('Building docker image...', (None, None, True), True)
    for line in c.build(path=os.path.join('test'),
                        rm=True,
                        tag='pracmln/testcontainer',
                        nocache=False):
        line = eval(line)
        if 'stream' in line:
            print line['stream'].decode('unicode_escape'),
    print colorize('Building docker image...', (None, None, True), True),
    print colorize('OK', (None, 'green', True), True)
    

if __name__ == '__main__':

    archs = ["win32", "linux_amd64", "linux_i386", "macosx", "macosx64"]

    args = sys.argv[1:]

    if '--help' in args:        
        print "PRACMLNs Apps Generator\n\n"
        print "  usage: make_apps [--arch=%s] [--cppbindings] " \
              "[--docs] [--test]\n" % "|".join(archs)
        print
        print
        exit(0)
    
    # determine architecture
    arch = None
    bits = 64 if "64" in platform.architecture()[0] else 32
    if len(args) > 0 and args[0].startswith("--arch="):
        arch = args[0][len("--arch="):].strip()
        args = args[1:]
    elif platform.mac_ver()[0] != "":
        arch = "macosx" if bits == 32 else "macosx64"
    elif platform.win32_ver()[0] != "":
        arch = "win32"
    elif platform.dist()[0] != "":
        arch = "linux_i386" if bits == 32 else "linux_amd64"
    if arch is None:
        print "Could not automatically determine your system's architecture." \
              " Please supply the --arch argument"
        sys.exit(1)
    if arch not in archs:
        print "Unknown architecture '%s'" % arch
        sys.exit(1)

    if '--test' in args:
        print 'testing pracmln installation only. no targets will be built'
        test()
        print 'testing finished'
        exit(0)

    check_dependencies()

    if '--docs' in args:
        build_docs()
        print

    buildlib = False
    if "--cppbindings" in args:
        buildlib = True

    print 'Removing old app folder...'
    shutil.rmtree('apps', ignore_errors=True)

    if not os.path.exists("apps"):
        os.mkdir("apps")

    print "\nCreating application files for %s..." % arch
    isWindows = "win" in arch
    isMacOSX = "macosx" in arch
    preamble = "@echo off\r\n" if isWindows else "#!/bin/sh\n"
    allargs = '%*' if isWindows else '"$@"'
    pathsep = os.path.pathsep
    
    for app in python_apps:
        filename = os.path.join("apps", "%s%s" % (app["name"],
                                                  {True: ".bat",
                                                   False: ""}[isWindows]))
        print "  %s" % filename
        f = file(filename, "w")
        f.write(preamble)
        f.write("python -O \"%s\" %s\n" % (adapt(app["script"], arch),
                                           allargs))
        f.close()
        if not isWindows:
            os.chmod(filename,
                     stat.S_IRUSR |
                     stat.S_IWUSR |
                     stat.S_IXUSR |
                     stat.S_IRGRP |
                     stat.S_IXGRP |
                     stat.S_IROTH |
                     stat.S_IXOTH)

    pracmln_test_script_src = os.path.join('test', 'pracmln-test.sh')
    pracmln_test_script_dest = os.path.join('apps', 'pracmln-test.sh')

    if not isWindows and not isMacOSX and os.path.exists(pracmln_test_script_src):
        shutil.copyfile(pracmln_test_script_src, pracmln_test_script_dest)
        os.chmod(pracmln_test_script_dest,
                 stat.S_IRUSR |
                 stat.S_IWUSR |
                 stat.S_IXUSR |
                 stat.S_IRGRP |
                 stat.S_IXGRP |
                 stat.S_IROTH |
                 stat.S_IXOTH)
    print

    # write shell script for environment setup
    appsDir = adapt("$PRACMLN_HOME/apps", arch)
    logutilsDir = adapt("$PRACMLN_HOME/3rdparty/logutils-0.3.3", arch)

    # make the experiments dir
    if not os.path.exists('experiments'):
        os.mkdir('experiments')

    extraExports = None
    if "win" not in arch and buildlib:
        extraExports = buildLibpracmln()

    if "win" not in arch:
        f = file("env.sh", "w")
        f.write('#!/bin/bash\n')
        f.write("export PATH=$PATH:%s\n" % appsDir)
        f.write("export PYTHONPATH=$PYTHONPATH:%s\n" % logutilsDir)
        f.write("export PRACMLN_HOME=%s\n" % adapt("$PRACMLN_HOME", arch))
        f.write("export PYTHONPATH=$PRACMLN_HOME:$PYTHONPATH\n")
        f.write("export PRACMLN_EXPERIMENTS=%s\n" %
                adapt(os.path.join("$PRACMLN_HOME", 'experiments'), arch))
        if extraExports:
            f.write(extraExports)
        f.close()
        print 'Now, to set up your environment type:'
        print '    source env.sh'
        print
        print 'To permantly configure your environment, add this line to ' \
              'your shell\'s initialization script (e.g. ~/.bashrc):'
        print '    source %s' % adapt("$PRACMLN_HOME/env.sh", arch)
        print
    else:
        pypath = ';'.join([adapt("$PRACMLN_HOME", arch), logutilsDir])
        f = file("env.bat", "w")
        f.write("@ECHO OFF\n")
        f.write('SETX PATH "%%PATH%%;%s"\r\n' % appsDir)
        f.write('SETX PRACMLN_HOME "%s"\r\n' % adapt("$PRACMLN_HOME", arch))
        f.write('SETX PYTHONPATH "%%PYTHONPATH%%;%s"\r\n' % pypath)
        f.write('SETX PRACMLN_EXPERIMENTS "%s"\r\n' %
                adapt(os.path.join("$PRACMLN_HOME", 'experiments'), arch))
        f.close()
        print 'To temporarily set up your environment for the current ' \
              'session, type:'
        print '    env.bat'
        print
        print 'To permanently configure your environment, use Windows ' \
              'Control Panel to set the following environment variables:'
        print '  To the PATH variable add the directory "%s"' % appsDir
        print 'Should any of these variables not exist, simply create them.'
