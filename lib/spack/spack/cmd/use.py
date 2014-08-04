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
import argparse
import llnl.util.tty as tty
import spack

description ="Add package to environment using dotkit."

def setup_parser(subparser):
    subparser.add_argument(
        'spec', nargs=argparse.REMAINDER, help='Spec of package to add.')


def print_help():
    tty.msg("Spack dotkit support is not initialized.",
            "",
            "To use dotkit with Spack, you must first run the command",
            "below, which you can copy and paste:",
            "",
            "For bash:",
            "    . %s/setup-env.bash" % spack.share_path,
            "",
            "ksh/csh/tcsh shells are currently unsupported",
            "")


def use(parser, args):
    print_help()