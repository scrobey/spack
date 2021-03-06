##############################################################################
# Copyright (c) 2013, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Written by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://scalability-llnl.github.io/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License (as published by
# the Free Software Foundation) version 2.1 dated February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
import os
import re
import shutil
import tempfile

import llnl.util.tty as tty
from llnl.util.filesystem import *

import spack
import spack.config
import spack.error
import spack.util.crypto as crypto
from spack.util.compression import decompressor_for


STAGE_PREFIX = 'spack-stage-'


class Stage(object):
    """A Stage object manaages a directory where an archive is downloaded,
       expanded, and built before being installed.  It also handles downloading
       the archive.  A stage's lifecycle looks like this:

       Stage()
         Constructor creates the stage directory.
       fetch()
         Fetch a source archive into the stage.
       expand_archive()
         Expand the source archive.
       <install>
         Build and install the archive.  This is handled by the Package class.
       destroy()
         Remove the stage once the package has been installed.

       If spack.use_tmp_stage is True, spack will attempt to create stages
       in a tmp directory.  Otherwise, stages are created directly in
       spack.stage_path.

       There are two kinds of stages: named and unnamed.  Named stages can
       persist between runs of spack, e.g. if you fetched a tarball but
       didn't finish building it, you won't have to fetch it again.

       Unnamed stages are created using standard mkdtemp mechanisms or
       similar, and are intended to persist for only one run of spack.
    """

    def __init__(self, url, **kwargs):
        """Create a stage object.
           Parameters:
             url     URL of the archive to be downloaded into this stage.

             name    If a name is provided, then this stage is a named stage
                     and will persist between runs (or if you construct another
                     stage object later).  If name is not provided, then this
                     stage will be given a unique name automatically.
        """
        self.name = kwargs.get('name')
        self.mirror_path = kwargs.get('mirror_path')

        self.tmp_root = find_tmp_root()
        self.url = url

        self.path = None
        self._setup()


    def _cleanup_dead_links(self):
        """Remove any dead links in the stage directory."""
        for file in os.listdir(spack.stage_path):
            path = join_path(spack.stage_path, file)
            if os.path.islink(path):
                real_path = os.path.realpath(path)
                if not os.path.exists(path):
                    os.unlink(path)


    def _need_to_create_path(self):
        """Makes sure nothing weird has happened since the last time we
           looked at path.  Returns True if path already exists and is ok.
           Returns False if path needs to be created.
        """
        # Path doesn't exist yet.  Will need to create it.
        if not os.path.exists(self.path):
            return True

        # Path exists but points at something else.  Blow it away.
        if not os.path.isdir(self.path):
            os.unlink(self.path)
            return True

        # Path looks ok, but need to check the target of the link.
        if os.path.islink(self.path):
            real_path = os.path.realpath(self.path)
            real_tmp  = os.path.realpath(self.tmp_root)

            if spack.use_tmp_stage:
                # If we're using a tmp dir, it's a link, and it points at the right spot,
                # then keep it.
                if (real_path.startswith(real_tmp) and os.path.exists(real_path)):
                    return False
                else:
                    # otherwise, just unlink it and start over.
                    os.unlink(self.path)
                    return True

            else:
                # If we're not tmp mode, then it's a link and we want a directory.
                os.unlink(self.path)
                return True

        return False


    def _setup(self):
        """Creates the stage directory.
           If spack.use_tmp_stage is False, the stage directory is created
           directly under spack.stage_path.

           If spack.use_tmp_stage is True, this will attempt to create a
           stage in a temporary directory and link it into spack.stage_path.
           Spack will use the first writable location in spack.tmp_dirs to
           create a stage.  If there is no valid location in tmp_dirs, fall
           back to making the stage inside spack.stage_path.
        """
        # Create the top-level stage directory
        mkdirp(spack.stage_path)
        self._cleanup_dead_links()

        # If this is a named stage, then construct a named path.
        if self.name is not None:
            self.path = join_path(spack.stage_path, self.name)

        # If this is a temporary stage, them make the temp directory
        tmp_dir = None
        if self.tmp_root:
            if self.name is None:
                # Unnamed tmp root.  Link the path in
                tmp_dir = tempfile.mkdtemp('', STAGE_PREFIX, self.tmp_root)
                self.name = os.path.basename(tmp_dir)
                self.path = join_path(spack.stage_path, self.name)
                if self._need_to_create_path():
                    os.symlink(tmp_dir, self.path)

            else:
                if self._need_to_create_path():
                    tmp_dir = tempfile.mkdtemp('', STAGE_PREFIX, self.tmp_root)
                    os.symlink(tmp_dir, self.path)

        # if we're not using a tmp dir, create the stage directly in the
        # stage dir, rather than linking to it.
        else:
            if self.name is None:
                self.path = tempfile.mkdtemp('', STAGE_PREFIX, spack.stage_path)
                self.name = os.path.basename(self.path)
            else:
                if self._need_to_create_path():
                    mkdirp(self.path)

        # Make sure we can actually do something with the stage we made.
        ensure_access(self.path)


    @property
    def archive_file(self):
        """Path to the source archive within this stage directory."""
        paths = [os.path.join(self.path, os.path.basename(self.url))]
        if self.mirror_path:
            paths.append(os.path.join(self.path, os.path.basename(self.mirror_path)))

        for path in paths:
            if os.path.exists(path):
                return path
        return None


    @property
    def expanded_archive_path(self):
        """Returns the path to the expanded archive directory if it's expanded;
           None if the archive hasn't been expanded.
        """
        if not self.archive_file:
            return None

        for file in os.listdir(self.path):
            archive_path = join_path(self.path, file)
            if os.path.isdir(archive_path):
                return archive_path
        return None


    def chdir(self):
        """Changes directory to the stage path.  Or dies if it is not set up."""
        if os.path.isdir(self.path):
            os.chdir(self.path)
        else:
            tty.die("Setup failed: no such directory: " + self.path)


    def fetch_from_url(self, url):
        # Run curl but grab the mime type from the http headers
        headers = spack.curl('-#',        # status bar
                             '-O',        # save file to disk
                             '-D', '-',   # print out HTML headers
                             '-L', url,
                             return_output=True, fail_on_error=False)

        if spack.curl.returncode != 0:
            # clean up archive on failure.
            if self.archive_file:
                os.remove(self.archive_file)

            if spack.curl.returncode == 60:
                # This is a certificate error.  Suggest spack -k
                raise FailedDownloadError(
                    url,
                    "Curl was unable to fetch due to invalid certificate. "
                    "This is either an attack, or your cluster's SSL configuration "
                    "is bad.  If you believe your SSL configuration is bad, you "
                    "can try running spack -k, which will not check SSL certificates."
                    "Use this at your own risk.")

        # Check if we somehow got an HTML file rather than the archive we
        # asked for.  We only look at the last content type, to handle
        # redirects properly.
        content_types = re.findall(r'Content-Type:[^\r\n]+', headers)
        if content_types and 'text/html' in content_types[-1]:
            tty.warn("The contents of " + self.archive_file + " look like HTML.",
                     "The checksum will likely be bad.  If it is, you can use",
                     "'spack clean --dist' to remove the bad archive, then fix",
                     "your internet gateway issue and install again.")


    def fetch(self):
        """Downloads the file at URL to the stage.  Returns true if it was downloaded,
           false if it already existed."""
        self.chdir()
        if self.archive_file:
            tty.msg("Already downloaded %s." % self.archive_file)

        else:
            urls = [self.url]
            if self.mirror_path:
                urls = ["%s/%s" % (m, self.mirror_path) for m in _get_mirrors()] + urls

            for url in urls:
                tty.msg("Trying to fetch from %s" % url)
                self.fetch_from_url(url)
                if self.archive_file:
                    break

        if not self.archive_file:
            raise FailedDownloadError(url)

        return self.archive_file


    def check(self, digest):
        """Check the downloaded archive against a checksum digest"""
        checker = crypto.Checker(digest)
        if not checker.check(self.archive_file):
            raise ChecksumError(
                "%s checksum failed for %s." % (checker.hash_name, self.archive_file),
                "Expected %s but got %s." % (digest, checker.sum))


    def expand_archive(self):
        """Changes to the stage directory and attempt to expand the downloaded
           archive.  Fail if the stage is not set up or if the archive is not yet
           downloaded.
        """
        self.chdir()
        if not self.archive_file:
            tty.die("Attempt to expand archive before fetching.")

        decompress = decompressor_for(self.archive_file)
        decompress(self.archive_file)


    def chdir_to_archive(self):
        """Changes directory to the expanded archive directory.
           Dies with an error if there was no expanded archive.
        """
        path = self.expanded_archive_path
        if not path:
            tty.die("Attempt to chdir before expanding archive.")
        else:
            os.chdir(path)
            if not os.listdir(path):
                tty.die("Archive was empty for %s" % self.name)


    def restage(self):
        """Removes the expanded archive path if it exists, then re-expands
           the archive.
        """
        if not self.archive_file:
            tty.die("Attempt to restage when not staged.")

        if self.expanded_archive_path:
            shutil.rmtree(self.expanded_archive_path, True)
        self.expand_archive()


    def destroy(self):
        """Remove this stage directory."""
        remove_linked_tree(self.path)

        # Make sure we don't end up in a removed directory
        try:
            os.getcwd()
        except OSError:
            os.chdir(os.path.dirname(self.path))


def _get_mirrors():
    """Get mirrors from spack configuration."""
    config = spack.config.get_config()

    mirrors = []
    sec_names = config.get_section_names('mirror')
    for name in sec_names:
        mirrors.append(config.get_value('mirror', name, 'url'))
    return mirrors


def ensure_access(file=spack.stage_path):
    """Ensure we can access a directory and die with an error if we can't."""
    if not can_access(file):
        tty.die("Insufficient permissions for %s" % file)


def remove_linked_tree(path):
    """Removes a directory and its contents.  If the directory is a symlink,
       follows the link and reamoves the real directory before removing the
       link.
    """
    if os.path.exists(path):
        if os.path.islink(path):
            shutil.rmtree(os.path.realpath(path), True)
            os.unlink(path)
        else:
            shutil.rmtree(path, True)


def purge():
    """Remove all build directories in the top-level stage path."""
    if os.path.isdir(spack.stage_path):
        for stage_dir in os.listdir(spack.stage_path):
            stage_path = join_path(spack.stage_path, stage_dir)
            remove_linked_tree(stage_path)


def find_tmp_root():
    if spack.use_tmp_stage:
        for tmp in spack.tmp_dirs:
            try:
                # Replace %u with username
                expanded = expand_user(tmp)

                # try to create a directory for spack stuff
                mkdirp(expanded)

                # return it if successful.
                return expanded

            except OSError:
                continue

    return None


class FailedDownloadError(spack.error.SpackError):
    """Raised wen a download fails."""
    def __init__(self, url, msg=""):
        super(FailedDownloadError, self).__init__(
            "Failed to fetch file from URL: %s" % url, msg)
        self.url = url


class ChecksumError(spack.error.SpackError):
    """Raised when archive fails to checksum."""
    def __init__(self, message, long_msg):
        super(ChecksumError, self).__init__(message, long_msg)
