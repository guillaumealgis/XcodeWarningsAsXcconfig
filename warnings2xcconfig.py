#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, absolute_import, division,
                        print_function)

import argparse
import itertools
import plistlib
import re
import tempfile
from os import path

from subprocess import check_output, check_call

# These settings are used for the 'strict' defaults style.
# All other settings values not explicitely defined here are inherited from
# the 'aggressive' style.
# The goal is to get as strict as possible, without making day-to-day
# development with these warnings a nightmare. This is intended to be
# community driven, do not hesitate to submit a PR if you feel one setting
# should have a stricter or looser default value.
#
# See https://pewpewthespells.com/blog/buildsettings.html for a description
# of each setting effect.
STRICT_DEFAULTS_EXCEPTIONS = {
    # https://openradar.appspot.com/radar?id=5907704967069696
    'CLANG_WARN_OBJC_REPEATED_USE_OF_WEAK': 'NO',

    # It's sometime useful to test a few things in debug build
    # Maybe use `YES` for release builds
    'GCC_TREAT_WARNINGS_AS_ERRORS': 'NO',

    # Doesn't play nice with Apple Frameworks
    'GCC_WARN_PEDANTIC': 'NO',

    # Don't need that with Objective-C 2.0
    'CLANG_WARN_OBJC_MISSING_PROPERTY_SYNTHESIS': 'NO',

    # Probably a bit controversial, but not uncommon to ignore some parameters
    # in Apple delegates methods
    'GCC_WARN_UNUSED_PARAMETER': 'NO',
}

###############################################################################

# Those are settings where 'YES' is not the most aggressive value
AGGRESSIVE_DEFAULTS_EXCEPTIONS = {
    'GCC_WARN_INHIBIT_ALL_WARNINGS': 'NO',
    'SWIFT_SUPPRESS_WARNINGS': 'NO',
}

# Clang Analyzer flags which are either too noisy, returns too much
# false-positives, or are already included in Xcode build settings
IGNORED_CLANG_ANALYZER_FLAGS = [
    # Too much false positives
    'alpha.clone.CloneChecker',
    'alpha.deadcode.UnreachableCode',
]

XCODE_REL_PROJECT_TEMPLATE_INFO_PATH = ('Contents/Developer/Library/Xcode/'
                                        'Templates/Project Templates/Base/'
                                        'Base_ProjectSettings.xctemplate/'
                                        'TemplateInfo.plist')


# Grabbed from https://stackoverflow.com/a/20037408/404321
def flatmap(func, *iterable):
    return itertools.chain.from_iterable(map(func, *iterable))


# Grabbed from https://stackoverflow.com/a/953097/404321
def flatten(list_of_lists):
    return list(itertools.chain.from_iterable(list_of_lists))


class XcspecOptionsGroup(object):
    def __init__(self, tool_name, group_name):
        self.tool_name = tool_name
        self.group_name = group_name
        self.options = []

    @property
    def display_name(self):
        display_names = {
            'WarningsObjCARC': 'Warnings - Objective C and ARC',
            'WarningsPolicy': 'Warnings - Warning Policies',
            'WarningsCXX': 'Warnings - C++',
            'WarningsObjC': 'Warnings - Objective C',
            'Warnings': 'Warnings - All languages',

            'LanguageModules': 'Language - Modules',

            'SAObjCCheckers': 'Issues - Objective C',
            'SASecurityCheckers': 'Issues - Security',
            'SAAppleAPICheckers': 'Issues - Apple APIs',
            'SACheckers': 'Generic Issues',
            'SAPolicy': 'Analysis Policy',
            'UBSANPolicy': 'Undefined Behavior Sanitizer',
        }

        name = self.tool_name + ' - '
        if self.group_name in display_names:
            name += display_names[self.group_name]
        else:
            name += self.group_name

        return name

    def format_for_xcconfig(self, default_values=None, add_doc=False):
        xcconfig_string = '// {}\n'.format(self.display_name)

        for option in self.options:
            xcconfig_string += option.format_for_xcconfig(
                default_values=default_values,
                add_doc=add_doc
            )

        return xcconfig_string


class XcspecOption(object):
    def __init__(self, xcspec_dict):
        self.from_xspec_dict(xcspec_dict)
        self.xcode_default_value = None
        self.strict_default_value = None

    def from_xspec_dict(self, xcspec_dict):
        self.name = xcspec_dict['Name']
        self.display_name = xcspec_dict.get('DisplayName')
        self.description = xcspec_dict.get('Description')
        self.type = xcspec_dict['Type']
        self.values = xcspec_dict.get('Values')
        self.clang_default_value = xcspec_dict.get('DefaultValue')
        self.command_line_args = xcspec_dict.get('CommandLineArgs')

    @property
    def aggressive_default_value(self):
        if self.name in AGGRESSIVE_DEFAULTS_EXCEPTIONS:
            return AGGRESSIVE_DEFAULTS_EXCEPTIONS[self.name]

        default_value = None
        if self.type == 'Boolean':
            default_value = self.aggressive_default_bool_value()
        elif self.type == 'Enumeration':
            default_value = self.aggressive_default_enum_value(self.values)

        if default_value is None:
            msg = ('Unknown default value for {} (Type : {}; Values : {})'
                   .format(self.name, self.type, self.values))
            raise NotImplementedError(msg)

        return default_value

    @staticmethod
    def aggressive_default_bool_value():
        return 'YES'

    @staticmethod
    def aggressive_default_enum_value(values):
        if values == ['YES', 'NO']:
            return 'YES'
        elif 'YES_AGGRESSIVE' in values:
            return 'YES_AGGRESSIVE'
        elif 'YES_ERROR' in values:
            return 'YES_ERROR'
        elif set(values) == set(['YES', 'YES_NONAGGRESSIVE', 'NO']):
            return 'YES'
        elif set(values) == set(['shallow', 'deep']):
            return 'deep'

        return None

    def _default_value_for_style(self, style):
        if style == 'clang':
            value = self.clang_default_value

        elif style == 'xcode':
            value = self.xcode_default_value
            if value is None:
                value = self.clang_default_value

        elif style == 'strict':
            if self.name in STRICT_DEFAULTS_EXCEPTIONS:
                value = STRICT_DEFAULTS_EXCEPTIONS[self.name]
            else:
                value = self.aggressive_default_value

        elif style == 'aggressive':
            value = self.aggressive_default_value

        else:
            if self.type == 'Boolean':
                value = 'YES | NO'
            elif self.type == 'Enumeration':
                value = ' | '.join(self.values)
            else:
                value = self.type

            value = '// {}'.format(value)

        return value

    @property
    def clang_analyzer_flags(self):
        if not self.command_line_args:
            return []

        args = flatten(self.command_line_args.values())
        flags = [arg for arg in args if not arg.startswith('-')]

        return flags

    def format_for_xcconfig(self, default_values=None, add_doc=False):
        value = self._default_value_for_style(default_values)

        opt_str = ''

        if add_doc and self.description:
            name = self.display_name
            doc = self.description
            opt_str += '// {}: {}\n'.format(name, doc)

        opt_str += '{} = {}\n'.format(self.name, value)

        return opt_str


class XSpecParser(object):
    def __init__(self, filepath):
        self._open_xcspec(filepath)

    def __exit__(self, exc_type, exc_value, traceback):
        self._xcspec_file.close()

    def _open_xcspec(self, file_path):
        self._xcspec_file = tempfile.NamedTemporaryFile()

        # Apple uses the old NeXTSTEP format for its xcspec, convert it to
        # xml with plutil
        check_call(['plutil', '-convert', 'xml1', file_path,
                    '-o', self._xcspec_file.name])

        self.xcspec_root = plistlib.readPlist(self._xcspec_file)

    def _get_tool_with_id(self, tool_identifier):
        xcspec_tool = None
        for tool in self.xcspec_root:
            if tool['Identifier'] == tool_identifier:
                xcspec_tool = tool

        if not xcspec_tool:
            raise Exception('Found no tool with identifier {} in '
                            'xcspec'.format(tool_identifier))

        # Inherit properties of the 'BasedOn' tool, if needed
        if 'BasedOn' in xcspec_tool:
            based_on_tool = self._get_tool_with_id(xcspec_tool['BasedOn'])
            full_tool = based_on_tool.copy()
            full_tool.update(xcspec_tool)
            xcspec_tool = full_tool

        return xcspec_tool

    def parse_options(self, tool_identifier, category_filter=None):
        if category_filter:
            category_filter = re.compile(category_filter)

        xcspec_tool = self._get_tool_with_id(tool_identifier)
        xcspec_tool_name = xcspec_tool['Name']
        xcspec_options = xcspec_tool['Options']

        options_groups = {}
        for xcspec_option in xcspec_options:
            if 'Category' not in xcspec_option:
                continue

            category = xcspec_option['Category']

            if category_filter and not category_filter.search(category):
                continue

            if category not in options_groups:
                options_groups[category] = XcspecOptionsGroup(xcspec_tool_name,
                                                              category)

            option = XcspecOption(xcspec_option)
            options_groups[category].options.append(option)

        return options_groups.values()


class ClangAnalyzerFlag(object):
    def __init__(self, name, doc=None):
        self.name = name
        self.doc = doc

    def format_for_xcconfig(self):
        flag_str = '-Xclang -analyzer-checker -Xclang {}'.format(self.name)
        return flag_str


class ClangHelpParser(object):
    def __init__(self, clang_bin_path, all_xspec_options=None):
        self.clang_bin_path = clang_bin_path

        # Extract the command line flags from all build settings we already
        # have so we don't repeat the same options twice when building
        if all_xspec_options:
            self.skipped_flags = list(flatmap(
                lambda opt: opt.clang_analyzer_flags,
                all_xspec_options
            ))
        else:
            self.skipped_flags = []

        self.found_checkers = False
        self.partial_flag = None
        self.flags = []

    def parse_help(self):
        clang_help = check_output([
            self.clang_bin_path, '-cc1', '-analyzer-checker-help'
        ])

        for line in clang_help.splitlines():
            self.parse_line(line)

        return self.flags

    def parse_line(self, line):
        if line.startswith('CHECKERS'):
            self.found_checkers = True
            return

        if not self.found_checkers:
            return

        if self.partial_flag:
            flag = self.parse_doc_line(line)
        else:
            flag = self.parse_new_flag_line(line)

        if flag and self.is_flag_valid(flag):
            self.flags.append(flag)

    def parse_doc_line(self, line):
        self.partial_flag.doc = line.strip()
        flag = self.partial_flag
        self.partial_flag = None
        return flag

    def parse_new_flag_line(self, line):
        bits = line.split(None, 1)
        bits = [bit for bit in bits if bit != '']

        if len(bits) == 1:
            name = bits[0]
            self.partial_flag = ClangAnalyzerFlag(name)
            return None

        name, doc = bits
        flag = ClangAnalyzerFlag(name, doc)
        return flag

    def is_flag_valid(self, flag):
        if flag.name.startswith('debug.'):
            return False

        if flag.name in IGNORED_CLANG_ANALYZER_FLAGS:
            return False

        if flag.name in self.skipped_flags:
            return False

        return True


def load_xcode_defaults(xcode_path, options_groups):
    xcode_template_path = path.join(xcode_path,
                                    XCODE_REL_PROJECT_TEMPLATE_INFO_PATH)
    xcode_template_info = plistlib.readPlist(xcode_template_path)
    xcode_defaults = xcode_template_info['Project']['SharedSettings']

    for options_group in options_groups:
        for option in options_group.options:
            if option.name not in xcode_defaults:
                continue

            option.xcode_default_value = xcode_defaults[option.name]


def xcspec_optgroups_as_xcconfig(options_groups, default_values=None,
                                 add_doc=False):
    formatted_optgroups = ''
    for options_group in options_groups:
        formatted_optgroups += options_group.format_for_xcconfig(
            default_values=default_values,
            add_doc=add_doc
        )
        formatted_optgroups += '\n'

    return formatted_optgroups


def analyzer_flags_as_xcconfig(analyzer_flags, add_doc=False):
    if not analyzer_flags:
        return ''

    formatted_flags = '// Clang Analyzer Flags\n'

    if add_doc:
        for flag in analyzer_flags:
            formatted_flags += '// {}: {}\n'.format(flag.name, flag.doc)

    formatted_flags += 'WAX_ANALYZER_FLAGS ='
    for flag in analyzer_flags:
        formatted_flags += ' '
        formatted_flags += flag.format_for_xcconfig()
    formatted_flags += '\n'

    formatted_flags += '\n'
    formatted_flags += 'WARNING_CFLAGS = $(inherited) $(WAX_ANALYZER_FLAGS)'

    return formatted_flags


def generate_xcconfig(optgroups, analyzer_flags, default_values=None,
                      add_doc=False):
    header = ('// Generated using XcodeWarningsAsXcconfig\n'
              '// https://github.com/guillaumealgis/XcodeWarningsAsXcconfig\n'
              '\n')

    optgroups = xcspec_optgroups_as_xcconfig(
        optgroups,
        default_values=default_values,
        add_doc=add_doc
    )

    analyzer_flags = analyzer_flags_as_xcconfig(
        analyzer_flags,
        add_doc=add_doc
    )

    xcconfig = header + optgroups + analyzer_flags

    return xcconfig


def parse_script_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Extract warning flags from Xcode and format them into '
                    'a xcconfig file')
    parser.add_argument(
        '-x', '--xcode-path', action='store', metavar='PATH',
        help='path to the Xcode install to scan. If not specified, '
             '`xcode-select -p` will be used to find a suitable Xcode install')
    parser.add_argument(
        '-d', '--defaults', action='store', metavar='STYLE',
        choices=['none', 'clang', 'xcode', 'strict', 'aggressive'],
        help='default values for the options in the generated xcconfig file\n'
             '  - none: no default values\n'
             '  - clang: defaults used by the clang compiler\n'
             '  - xcode: defaults used by xcode when creating a new project\n'
             '  - strict: hand picked values to make your code safer without '
             'being too much of a hassle to fix\n'
             '  - aggressive: everything \'on\' '
             '(you probably don\'t want this)')
    parser.add_argument(
        '--no-swift', dest='swift', action='store_false',
        help='don\'t include Swift-related flags in the output')
    parser.add_argument(
        '--no-analyzer', dest='analyzer_flags', action='store_false',
        help='don\'t include Clang Analyzer checker flags in the output')
    parser.add_argument(
        '--doc', action='store_true',
        help='include documentation about the options in the generated '
             'xcconfig file, if available')

    args = parser.parse_args()

    # Default value for xcode-path if none is explicitly specified
    if args.xcode_path is None:
        xcode_path = check_output(['xcode-select', '-p'])
        xcode_path = xcode_path.strip()
        # import ipdb; ipdb.set_trace(context=5)
        xcode_path = xcode_path.replace('/Contents/Developer', '')
        args.xcode_path = xcode_path

    return args


def xcspec_path(xcode_path, xcplugin, xcspec=None):
    if not xcspec:
        xcspec = xcplugin

    path_template = ('Contents/PlugIns/Xcode3Core.ideplugin/Contents/'
                     'SharedSupport/Developer/Library/Xcode/Plug-ins/'
                     '{}.xcplugin/Contents/Resources/{}.xcspec')
    rel_path = path_template.format(xcplugin, xcspec)
    full_path = path.join(xcode_path, rel_path)

    return full_path


def default_toolchain_bin_path(xcode_path, bin_name):
    path_template = ('Contents/Developer/Toolchains/XcodeDefault.xctoolchain/'
                     'usr/bin/{}')
    rel_path = path_template.format(bin_name)
    full_path = path.join(xcode_path, rel_path)

    return full_path


def main():
    args = parse_script_args()

    clang_llvm_xcspec_path = xcspec_path(args.xcode_path, 'Clang LLVM 1.0')
    clang_llvm_parser = XSpecParser(clang_llvm_xcspec_path)
    options_groups = clang_llvm_parser.parse_options(
        'com.apple.compilers.llvm.clang.1_0.compiler',
        category_filter=r'^Warning'
    )

    if args.analyzer_flags:
        options_groups += clang_llvm_parser.parse_options(
            'com.apple.compilers.llvm.clang.1_0.compiler',
            category_filter=r'UBSANPolicy'
        )
        options_groups += clang_llvm_parser.parse_options(
            'com.apple.compilers.llvm.clang.1_0.analyzer'
        )

    if args.swift:
        swift_xcspec_path = xcspec_path(
            args.xcode_path, 'XCLanguageSupport', 'Swift'
        )
        swift_parser = XSpecParser(swift_xcspec_path)
        options_groups += swift_parser.parse_options(
            'com.apple.xcode.tools.swift.compiler',
            category_filter=r'^Warning'
        )

    load_xcode_defaults(args.xcode_path, options_groups)

    analyzer_flags = None
    if args.analyzer_flags:
        all_xspec_options = list(flatmap(lambda g: g.options, options_groups))
        clang_bin_path = default_toolchain_bin_path(args.xcode_path, 'clang')
        help_parser = ClangHelpParser(clang_bin_path, all_xspec_options)
        analyzer_flags = help_parser.parse_help()

    xcconfig = generate_xcconfig(
        options_groups,
        analyzer_flags,
        default_values=args.defaults,
        add_doc=args.doc
    )
    print(xcconfig)


if __name__ == "__main__":
    main()
