#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import os
import platform
import shutil
import stat
import sys
from importlib import util as imputil


if imputil.find_spec('logutils') is None:
    print('cannot find logutils. Please install by "sudo pip install logutils".')
    sys.exit(-1)
else:
    from logutils.colorize import ColorizingStreamHandler


def colorize(message, format, color=False):
    '''
    Returns the given message in a colorized format
    string with ANSI escape codes for colorized console outputs:
    - message:   the message to be formatted.
    - format:    triple containing format information:
                 (bg-color, fg-color, bf-boolean) supported colors are
                 'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'
    - color:     boolean determining whether or not the colorization
                 is to be actually performed.
    '''
    colorize.colorHandler = ColorizingStreamHandler(sys.stdout)
    if color is False: return message
    params = []
    (bg, fg, bold) = format
    if bg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[bg] + 40))
    if fg in colorize.colorHandler.color_map:
        params.append(str(colorize.colorHandler.color_map[fg] + 30))
    if bold:
        params.append('1')
    if params:
        message = ''.join((colorize.colorHandler.csi, ';'.join(params), 'm', message, colorize.colorHandler.reset))
    return message

python_apps = [
    {"name": "mlnquery", "script": "$PRACMLN_HOME/pracmln/mlnquery.py"},
    {"name": "mlnlearn", "script": "$PRACMLN_HOME/pracmln/mlnlearn.py"},
    {"name": "xval", "script": "$PRACMLN_HOME/pracmln/xval.py"}
]

def check_package(pkg):
    sys.stdout.write('checking dependency "{}"...'.format(pkg))
    if imputil.find_spec(pkg) is not None:
        sys.stdout.write(colorize('OK\n', (None, 'green', True), True))
        return True
    else:
        print(colorize('{0} was not found. Please install by "sudo pip install {0}"'.format(pkg), (None, 'yellow', True), True))
        return False


# check the package dependecies
def check_dependencies():
    with open('requirements.txt', 'r') as req:
        requirements = req.readlines()
        packages = [p.strip() for p in requirements]

    if not all([check_package(pkg) for pkg in packages]) and not ignoreimporterrors:
        print(colorize('One or more required package(s) could not be found. Make sure all dependencies are installed to properly use materials.', (None, 'red', True), True))


def adapt(name, archit):
    return name.replace("<ARCH>", archit).replace("$PRACMLN_HOME", os.path.abspath(".")).replace("/", os.path.sep)


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
    docspackages = [('sphinx', 'sphinx sphinxcontrib-bibtex', False)]
    print(colorize('Building documentation', (None, 'green', True), True))
    for pkg in docspackages:
        check_package(pkg)
    print()
    docs = adapt("cd $PRACMLN_HOME/doc && make html && cd -", architecture)
    os.system(docs)


def test():
    print(colorize('Checking docker...', (None, None, True), True), end=' ')
    if imputil.find_spec('docker') is not None:
        print(colorize('OK', (None, 'green', True), True))
    else:
        print(colorize('Docker is not installed. To install, conduct the following actions:', (None, 'red', True), True), end=' ')
        print('  wget https://get.docker.com/ | sh')
        print('  sudo groupadd docker')
        print('  sudo gpasswd -a $USER docker')
        print('  sudo service docker restart')
        print('  newgrp')
        print() 
        print('  # test docker')
        print('  docker run hello-world')
        print() 
        print('  # install python bindings')
        print('  sudo pip install docker-py')
        exit(-1)

    from docker import DockerClient
    c = DockerClient(base_url='unix://var/run/docker.sock')
    print(colorize('Building docker image...', (None, None, True), True))
    for line in c.build(path=os.path.join('test'),
                        rm=True,
                        tag='pracmln/testcontainer',
                        nocache=False):
        line = eval(line)
        if 'stream' in line:
            print(line['stream'].decode('unicode_escape'), end=' ')
    print(colorize('Building docker image...', (None, None, True), True), end=' ')
    print(colorize('OK', (None, 'green', True), True))


# determine architecture
def arch(argarchit=None):
    archit = None
    bits = 64 if "64" in platform.architecture()[0] else 32
    if argarchit is not None:
        archit=argarchit
    elif platform.mac_ver()[0] != "":
        archit = "macosx" if bits == 32 else "macosx64"
    elif platform.win32_ver()[0] != "":
        archit = "win32"
    elif sys.platform.startswith('linux'):
        archit = "linux_i386" if bits == 32 else "linux_amd64"
    if archit is None:
        print("Could not automatically determine your system's architecture. Please supply the --arch argument")
        sys.exit(1)
    if archit not in archits:
        print("Unknown architecture '{}'".format(archit))
        sys.exit(1)
    return archit

if __name__ == '__main__':
    archits = ["win32", "linux_amd64", "linux_i386", "macosx", "macosx64"]

    usage = 'PRACMLNs Apps Generator\n\n\tUsage: make_apps [--cppbindings] [--arch={}]\n'.format('|'.join(archits))
    parser = argparse.ArgumentParser(description=usage)
    parser.add_argument("-a", "--arch", dest="architecture", type=str, default=None, action="store", help="Specify architecture. Possible architectures: {}".format('|'.join(archits)))
    parser.add_argument("-c", "--cppbindings", dest="cppbindings", default=False, action="store_true", help="If this option is set, cpp bindings will be generated.")
    parser.add_argument("-d", "--docs", dest="docs", default=False, action="store_true", help="Build documentation.")
    parser.add_argument("-i", "--ignore", dest="ignore", default=False, action="store_true", help="Ignore import errors.")
    parser.add_argument("-t", "--test", dest="test", default=False, action="store_true", help="Run tests.")

    args = parser.parse_args()
    architecture = arch(args.architecture)
    ignoreimporterrors = args.ignore
    check_dependencies()

    if args.test:
        print('testing pracmln installation only. no targets will be built')
        test()
        print('testing finished')
        exit(0)

    if args.docs:
        build_docs()
        print()

    # updating apps folder
    shutil.rmtree('apps', ignore_errors=True)
    if not os.path.exists("apps"):
        os.mkdir("apps")

    print("\nCreating application files for {}...".format(architecture))
    isWindows = "win" in archits
    isMacOSX = "macosx" in archits
    preamble = "@echo off\r\n" if isWindows else "#!/bin/sh\n"
    allargs = '%*' if isWindows else '"$@"'
    pathsep = os.path.pathsep
    
    for app in python_apps:
        filename = os.path.join("apps", "{}{}".format(app["name"], {True: ".bat", False: ""}[isWindows]))
        print("  {}".format(filename))
        f = open(filename, "w")
        f.write(preamble)
        f.write("python3 -O \"{}\" {}\n".format(adapt(app["script"], architecture), allargs))
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
    print()

    # write shell script for environment setup
    appsDir = adapt("$PRACMLN_HOME/apps", architecture)

    # make the experiments dir
    if not os.path.exists('experiments'):
        os.mkdir('experiments')

    extraExports = None
    if "win" not in architecture and args.cppbindings:
        extraExports = buildLibpracmln()

    if "win" not in architecture:
        f = open("env.sh", "w")
        f.write('#!/bin/bash\n')
        f.write("export PATH=$PATH:{}\n".format(appsDir))
        f.write("export PRACMLN_HOME={}\n".format(adapt("$PRACMLN_HOME", architecture)))
        f.write("export PYTHONPATH=$PRACMLN_HOME:$PYTHONPATH\n")
        f.write("export PRACMLN_EXPERIMENTS={}\n".format(adapt(os.path.join("$PRACMLN_HOME", 'experiments'), architecture)))
        if extraExports:
            f.write(extraExports)
        f.close()
        print('Now, to set up your environment type:')
        print('    source env.sh')
        print()
        print('To permantly configure your environment, add this line to your shell\'s initialization script (e.g. ~/.bashrc):')
        print('    source {}'.format(adapt("$PRACMLN_HOME/env.sh", architecture)))
        print()
    else:
        f = open("env.bat", "w")
        f.write("@ECHO OFF\n")
        f.write('SETX PATH "%%PATH%%;{}"\r\n'.format(appsDir))
        f.write('SETX PRACMLN_HOME "{}"\r\n'.format(adapt("$PRACMLN_HOME", architecture)))
        f.write('SETX PRACMLN_EXPERIMENTS "{}"\r\n'.format(adapt(os.path.join("$PRACMLN_HOME", 'experiments'), architecture)))
        f.close()
        print('To temporarily set up your environment for the current session, type:')
        print('    env.bat')
        print()
        print('To permanently configure your environment, use Windows Control Panel to set the following environment variables:')
        print('  To the PATH variable add the directory "{}"'.format(appsDir))
        print('Should any of these variables not exist, simply create them.')
