#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools, VisualStudioBuildEnvironment
from conans.tools import replace_in_file
from conans.errors import ConanInvalidConfiguration
import os


class LibpqConan(ConanFile):
    name = "libpq"
    version = "10.4"
    description = "The library used by all the standard PostgreSQL tools."
    url = "https://github.com/bincrafters/conan-libpq"
    homepage = "https://www.postgresql.org/docs/current/static/libpq.html"
    license = "PostgreSQL"
    exports = ["LICENSE.md"]
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_zlib": [True, False],
        "with_openssl": [True, False]}
    default_options = {'shared': False, 'fPIC': True, 'with_zlib': False, 'with_openssl': False}
    _source_subfolder = "source_subfolder"
    _build_subfolder = None
    _autotools = None

    @property
    def pq_msvc_dir(self):
        return os.path.join(self._source_subfolder, 'src', 'tools', 'msvc')

    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC
            del self.options.shared

    def configure(self):
        del self.settings.compiler.libcxx

    def requirements(self):
        if self.options.with_zlib:
            self.requires.add("zlib/1.2.11@conan/stable")
        if self.options.with_openssl:
            self.requires.add("OpenSSL/1.0.2o@conan/stable")

    def source(self):
        source_url = "https://ftp.postgresql.org/pub/source"
        tools.get("{0}/v{1}/postgresql-{2}.tar.gz".format(source_url, self.version, self.version))
        extracted_dir = "postgresql-" + self.version
        os.rename(extracted_dir, self._source_subfolder)

    def _configure_autotools(self):
        if not self._autotools:
            self._autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
            self._build_subfolder = os.path.join(self.build_folder, "output")
            args = ['--without-readline']
            args.append('--with-zlib' if self.options.with_zlib else '--without-zlib')
            args.append('--with-openssl' if self.options.with_openssl else '--without-openssl')
            with tools.chdir(self._source_subfolder):
                self._autotools.configure(args=args)
        return self._autotools

    def build(self):
        if self.settings.os == "Windows":
            if self.settings.compiler == "Visual Studio":
                # Visual Studio: https://www.postgresql.org/docs/current/static/install-windows-full.html
                env = VisualStudioBuildEnvironment(self)
                with tools.environment_append(env.vars):
                    with tools.chdir(self.pq_msvc_dir):
                        self.run("build.bat")
            else:
                raise NotImplementedError("Windows compiler {!r} not implemented".format(str(self.settings.compiler)))
        elif self.settings.os in ["Linux", "Macos"]:
            autotools = self._configure_autotools()
            with tools.chdir(os.path.join(self._source_subfolder, "src", "common")):
                autotools.make()
            with tools.chdir(os.path.join(self._source_subfolder, "src", "interfaces", "libpq")):
                autotools.make()
        else:
            raise NotImplementedError("Compiler {!r} for os {!r} not available".format(str(self.settings.compiler), str(self.settings.os)))

    def package(self):
        if self.settings.os == "Windows":
            self._build_subfolder = os.path.join(self.build_folder, "output")
            msvc_dir = os.path.abspath(self.pq_msvc_dir)
            with tools.chdir(msvc_dir):
                # Modify install.pl file: https://stackoverflow.com/questions/46161246/cpan-install-moduleinstall-fails-passing-tests-strawberryperl/46162454?noredirect=1#comment79291874_46162454
                install_pl = os.path.join(msvc_dir, 'install.pl')
                replace_in_file(install_pl, "use Install qw(Install);", "use FindBin qw( $RealBin );\nuse lib $RealBin;\nuse Install qw(Install);")
                self.run("install %s" % self._build_subfolder)

            self.copy(pattern="*.dll", dst="bin", src=os.path.join(self._build_subfolder, "bin"))
            self.copy(pattern="*.lib", dst="bin", src=os.path.join(self._build_subfolder, "bin"))
            self.copy(pattern="*", dst="lib", src=os.path.join(self._build_subfolder, "lib"))
            self.copy(pattern="*.h", dst="include", src=os.path.join(self._build_subfolder, "include"))
            self.copy(pattern="*", dst="symbols", src=os.path.join(self._build_subfolder, "symbols"))
        else:
            autotools = self._configure_autotools()
            with tools.chdir(os.path.join(self._source_subfolder, "src", "common")):
                autotools.install()
            with tools.chdir(os.path.join(self._source_subfolder, "src", "interfaces", "libpq")):
                autotools.install()
            self.copy(pattern="*.h", dst="include", src=os.path.join(self._build_subfolder, "include"))
            self.copy(pattern="postgres_ext.h", dst="include", src=os.path.join(self._source_subfolder, "src", "include"))
            self.copy(pattern="pg_config_ext.h", dst="include", src=os.path.join(self._source_subfolder, "src", "include"))

            if self.settings.os == "Linux":
                pattern = "*.so*" if self.options.shared else "*.a"
            elif self.settings.os == "Macos":
                pattern = "*.dylib" if self.options.shared else "*.a"
            self.copy(pattern=pattern, dst="lib", src=os.path.join(self._build_subfolder, "lib"))

        self.copy(pattern="COPYRIGHT", dst="licenses", src=self._source_subfolder)

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        if self.settings.os == "Linux":
            self.cpp_info.libs.append("pthread")
        elif self.settings.os == "Windows":
            self.cpp_info.libs = ["libpq",]
            self.cpp_info.libs.append("ws2_32")
