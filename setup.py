# Copyright 2016-2018 Dirk Thomas
# Licensed under the Apache License, Version 2.0

import os
import sys

from setuptools import setup

if sys.platform == 'win32':
    print(
        "The Python package 'colcon-argcomplete' doesn't support Windows",
        file=sys.stderr)
    sys.exit(1)

if 'BUILD_DEBIAN_PACKAGE' not in os.environ:
    from pkg_resources import parse_version
    from setuptools import __version__ as setuptools_version
    minimum_version = '40.5.0'
    if parse_version(setuptools_version) < parse_version(minimum_version):
        print(
            "The Python package 'colcon-argcomplete' requires at least "
            'setuptools version {minimum_version}'.format_map(locals()),
            file=sys.stderr)
        sys.exit(1)

cmdclass = {}
try:
    from stdeb.command.sdist_dsc import sdist_dsc
except ImportError:
    pass
else:
    class CustomSdistDebCommand(sdist_dsc):
        """Weird approach to apply the Debian patches during packaging."""

        def run(self):  # noqa: D102
            from stdeb.command import sdist_dsc
            build_dsc = sdist_dsc.build_dsc

            def custom_build_dsc(*args, **kwargs):
                nonlocal build_dsc
                debinfo = self.get_debinfo()
                repackaged_dirname = \
                    debinfo.source + '-' + debinfo.upstream_version
                dst_directory = os.path.join(
                    self.dist_dir, repackaged_dirname, 'debian', 'patches')
                os.makedirs(dst_directory, exist_ok=True)
                # read patch
                with open('debian/patches/setup.cfg.patch', 'r') as h:
                    lines = h.read().splitlines()
                print(
                    "writing customized patch '%s'" %
                    os.path.join(dst_directory, 'setup.cfg.patch'))
                # write patch with modified path
                with open(
                    os.path.join(dst_directory, 'setup.cfg.patch'), 'w'
                ) as h:
                    for line in lines:
                        if line.startswith('--- ') or line.startswith('+++ '):
                            line = \
                                line[0:4] + repackaged_dirname + '/' + line[4:]
                        h.write(line + '\n')
                with open(os.path.join(dst_directory, 'series'), 'w') as h:
                    h.write('setup.cfg.patch\n')
                return build_dsc(*args, **kwargs)

            sdist_dsc.build_dsc = custom_build_dsc
            super().run()
    cmdclass['sdist_dsc'] = CustomSdistDebCommand

if 'BUILD_DEBIAN_PACKAGE' in os.environ:
    import distutils.command.install as distutils_install
    import inspect
    import shutil

    from setuptools.command.install import install

    src_base = 'completion'
    data_files = (
        ('share/colcon_argcomplete/hook', [
            'completion/colcon-argcomplete.bash',
            'completion/colcon-argcomplete.zsh']),
    )

    dst_prefix = None
    if os.path.exists('.pc/applied-patches'):
        # assuming this is a deb_dist build
        # use dst prefix for data files
        dst_prefix = os.path.join(
            os.getcwd(), 'debian/python3-colcon-argcomplete')

    class CustomInstallCommand(install):

        def run(self):
            global data_files
            # https://github.com/pypa/setuptools/blob/52aacd5b276fedd6849c3a648a0014f5da563e93/setuptools/command/install.py#L59-L67
            # Explicit request for old-style install?  Just do it
            if self.old_and_unmanageable or self.single_version_externally_managed:
                distutils_install.install.run(self)
            elif not self._called_from_setup(inspect.currentframe()):
                # Run in backward-compatibility mode to support bdist_* commands.
                distutils_install.install.run(self)
            else:
                super().do_egg_install()

            _foreach_data_file(
                self, data_files,
                'Copying {src} to {dst_dir}',
                _copy_data_file)

    def _foreach_data_file(command, data_files, msg, callback):
        global dst_prefix
        for dst_dir, srcs in data_files:
            if command.prefix is not None:
                dst_dir = os.path.join(command.prefix, dst_dir)
            if dst_prefix:
                dst_dir = os.path.join(dst_prefix) + dst_dir
            for src in srcs:
                dst = os.path.join(dst_dir, os.path.basename(src))
                try:
                    src = os.path.join(
                        os.path.dirname(os.path.realpath('setup.py')),
                        src)
                except OSError:
                    pass
                print(msg.format_map(locals()))
                if not command.dry_run:
                    callback(src, dst_dir, dst)

    def _copy_data_file(src, dst_dir, dst):
        _prepare_destination(src, dst_dir, dst)
        shutil.copy2(src, dst_dir)

    def _prepare_destination(src, dst_dir, dst):
        assert os.path.isfile(src), \
            "data file '{src}' not found".format_map(locals())
        assert os.path.isabs(dst_dir), \
            'Install command needs to be invoked with --prefix ' \
            'or the data files destination must be absolute'
        assert not os.path.isfile(dst_dir), \
            'data file destination directory must not be a file'
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        try:
            os.remove(dst)
        except FileNotFoundError:
            pass

    cmdclass['install'] = CustomInstallCommand

setup(cmdclass=cmdclass)
