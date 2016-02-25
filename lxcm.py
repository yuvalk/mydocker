#!/usr/bin/env python2.7
#
# Docker From Scratch Workshop
# Level 0 - starting a new process (no containment)
#
# Goal: We want our code to start a new linux process using the fork & exec model
#       i.e. running:
#                rd.py run /bin/sh
#            will fork a new process which will exec '/bin/sh', while the parent waits for it to finish.
#

from __future__ import print_function

import os
import uuid
import click
import linux
import tarfile


@click.group()
def cli():
    pass

def _get_image_path(image_name, image_dir, image_suffix='tar'):
    return os.path.join(image_dir, os.extsep.join([image_name, image_suffix]))

def _get_container_path(container_id, container_dir, *subdir_modules):
    return os.path.join(container_dir, container_id, *subdir_modules)

def create_container_root(image_name, image_dir, container_id, container_dir):
    image_path = _get_image_path(image_name, image_dir)
    container_root = _get_container_path(container_id, container_dir, 'rootfs')

    assert os.path.exists(image_path), "unable to locate image %s" % image_name

    if not os.path.exists(container_root):
        os.makedirs(container_root)

    with tarfile.open(image_path) as t:
        t.extractall(container_root, members=[m for m in t.getmembers() if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)])

    return container_root


def contain(command, image, image_dir, container_id, containers_dir):
    linux.unshare(linux.CLONE_NEWNS)
    linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)  # TODO: we added MS_REC here. wanna guess why?

    new_root = create_container_root(image, image_dir, container_id, containers_dir)
    print('Created a new root fs for our container: {}'.format(new_root))

    # TODO: time to say goodbye to the old mount namespace, see "man 2 unshare" to get some help
    #   HINT 1: there is no os.unshare(), time to use the linux module we made just for you!
    #   HINT 2: the linux module include both functions and constants! e.g. linux.CLONE_NEWNS

    # TODO: remember shared subtrees? (https://www.kernel.org/doc/Documentation/filesystems/sharedsubtree.txt)
    #       remount / as a private mount to avoid littering our host mount table

    # Create mounts (/proc, /sys, /dev) under new_root
    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs',
        linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')
    # Add some basic devices
    devpts_path = os.path.join(new_root, 'dev', 'pts')
    if not os.path.exists(devpts_path):
        os.makedirs(devpts_path)
        linux.mount('devpts', devpts_path, 'devpts', 0, '')
    for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
        os.symlink('/proc/self/fd/%d' % i, os.path.join(new_root, 'dev', dev))

    # TODO: add more device (e.g. null, zero, random, urandom) using os.mknode
    new_root = create_container_root(image, image_dir, container_id, containers_dir)

    os.chroot(new_root)
    os.chdir('/')
    os.execvp(command[0], command)


@cli.command()
@click.option('--image', '-i', help='Image name', default='busybox')
@click.option('--image-dir', help='Images directory', default='/workshop/images')
@click.option('--container-dir', help='Containers directory', default='/workshop/containers')
@click.argument('Command', required=True, nargs=-1)
def run(image, image_dir, container_dir, command):
    container_id = str(uuid.uuid4())
    pid = os.fork()
    if pid == 0:
        # This is the child, we need to exec the command
        contain(command, image, image_dir, container_id, container_dir)
    else:
        # This is the parent, pid contains the PID of the forked process
        _, status = os.waitpid(pid, 0)  # wait for the forked child, fetch the exit status
        print('{} exited with status {}'.format(pid, status))


if __name__ == '__main__':
    cli()
