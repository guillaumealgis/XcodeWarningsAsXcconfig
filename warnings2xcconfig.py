#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, absolute_import, division,
                        print_function)

import tempfile
import plistlib
import argparse
import re
from os import path

from subprocess import check_output, check_call

# These settings are used for the 'strict' defaults style.
# All other settings values not explicitely defined here are inherited from
# the 'aggressive' style.
# The goal is to get as strict as possible, without making day-to-day
# development with these warnings a nightmare. This is intended to be
# community driven, do not hesitate to submit a PR if you feel one setting
# should have a stricter or looser default value.
STRICT_DEFAULTS_EXCEPTIONS = {
    'CLANG_WARN_OBJC_REPEATED_USE_OF_WEAK': 'NO',
    'GCC_TREAT_WARNINGS_AS_ERRORS': 'NO',
    'GCC_WARN_PEDANTIC': 'NO',
    'CLANG_WARN_OBJC_MISSING_PROPERTY_SYNTHESIS': 'NO',
# Those are settings where 'YES' is not the most aggressive value
AGGRESSIVE_DEFAULTS_EXCEPTIONS = {
    'GCC_WARN_INHIBIT_ALL_WARNINGS': 'NO'
}


class XcspecOptionsGroup(object):
    def __init__(self, tool_name, group_name):
        super(XcspecOptionsGroup, self).__init__()
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

            'SAObjCCheckers': 'Issues - Objective C',
            'SASecurityCheckers': 'Issues - Security',
            'SACheckers': 'Generic Issues',
            'SAPolicy': 'Analysis Policiy',
        }

        name = self.tool_name + ' - '
        if self.group_name in display_names:
            name += display_names[self.group_name]
        else:
            name += self.group_name

        return name

    def format_as_xcconfig(self, default_values=None, add_doc=False):
        s = '// {}\n'.format(self.display_name)

        for option in self.options:
            s += option.format_as_xcconfig(default_values=default_values, add_doc=add_doc)

        return s


class XcspecOption(object):
    def __init__(self, xcspec_dict):
        super(XcspecOption, self).__init__()
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

    @property
    def aggressive_default_value(self):
        if self.name in AGGRESSIVE_DEFAULTS_EXCEPTIONS:
            return AGGRESSIVE_DEFAULTS_EXCEPTIONS[self.name]

        if self.type == 'Boolean':
            return 'YES'
        elif self.type == 'Enumeration':
            if self.values == ['YES', 'NO']:
                return 'YES'
            elif 'YES_AGGRESSIVE' in self.values:
                return 'YES_AGGRESSIVE'
            elif 'YES_ERROR' in self.values:
                return 'YES_ERROR'
            elif set(self.values) == set(['shallow', 'deep']):
                return 'deep'
        raise Exception('Unknown aggressive value for {} ({})'
                        .format(self.name, self.type))

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

    def format_as_xcconfig(self, default_values=None, add_doc=False):
        value = self._default_value_for_style(default_values)

        opt_str = ''

        if add_doc and self.description:
            opt_str += '// {}: {}\n'.format(self.display_name, self.description)

        opt_str += '{} = {}\n'.format(self.name, value)

        return opt_str


class XSpecParser(object):
    def __init__(self, filepath):
        super(XSpecParser, self).__init__()
        self._open_xcspec(filepath)

    def __exit__(self, exc_type, exc_value, traceback):
        self._xcspec_file.close()

    def _open_xcspec(self, xcspec_path):
        self._xcspec_file = tempfile.NamedTemporaryFile()

        # Apple uses the old NeXTSTEP format for its xcspec, convert it to
        # xml with plutil
        check_call(['plutil', '-convert', 'xml1', xcspec_path, '-o',
                    self._xcspec_file.name])

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


def import_xcode_defaults_into_options(xcode_path, options_groups):
    XCODE_REL_PROJECT_TEMPLATE_INFO_PATH = 'Contents/Developer/Library/Xcode/Templates/Project Templates/Base/Base.xctemplate/TemplateInfo.plist'
    xcode_template_path = path.join(xcode_path,
                                    XCODE_REL_PROJECT_TEMPLATE_INFO_PATH)
    xcode_template_info = plistlib.readPlist(xcode_template_path)
    xcode_defaults = xcode_template_info['Project']['SharedSettings']

    for options_group in options_groups:
        for option in options_group.options:
            if option.name not in xcode_defaults:
                continue

            option.xcode_default_value = xcode_defaults[option.name]


def format_xcspec_options_groups_as_xcconfig(options_groups, default_values=None, add_doc=False):
    xcconfig = '// Generated using XcodeWarningsAsXcconfig\n'
    xcconfig += '// https://github.com/guillaume-algis/XcodeWarningsAsXcconfig\n'
    xcconfig += '\n'

    for options_group in options_groups:
        xcconfig += options_group.format_as_xcconfig(default_values=default_values, add_doc=add_doc)
        xcconfig += '\n'

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
             '  - aggressive: everything \'on\' (you probably don\'t want this)')
    parser.add_argument(
        '--doc', action='store_true',
        help='include documentation about the options in the generated '
             'xcconfig file, if available')

    args = parser.parse_args()

    # Default value for xcode-path if none is explicitly specified
    if args.xcode_path is None:
        xcode_path = check_output(['xcode-select', '-p'])
        xcode_path = xcode_path.strip()
        xcode_path = xcode_path.replace('/Contents/Developer', '')
        args.xcode_path = xcode_path

    return args


def clang_llvm_xcspec_path(xcode_path):
    XCODE_REL_CLANG_LLVM_XCSPEC_PATH = 'Contents/PlugIns/Xcode3Core.ideplugin/Contents/SharedSupport/Developer/Library/Xcode/Plug-ins/Clang LLVM 1.0.xcplugin/Contents/Resources/Clang LLVM 1.0.xcspec'
    clang_llvm_xcspec_path = path.join(xcode_path,
                                       XCODE_REL_CLANG_LLVM_XCSPEC_PATH)
    return clang_llvm_xcspec_path


def main():
    args = parse_script_args()

    xcspec_path = clang_llvm_xcspec_path(args.xcode_path)

    parser = XSpecParser(xcspec_path)
    options_groups = parser.parse_options('com.apple.compilers.llvm.clang.1_0.compiler', category_filter=r'^Warning')
    options_groups += parser.parse_options('com.apple.compilers.llvm.clang.1_0.analyzer')

    import_xcode_defaults_into_options(args.xcode_path, options_groups)

    print(format_xcspec_options_groups_as_xcconfig(options_groups, default_values=args.defaults, add_doc=args.doc))

if __name__ == "__main__":
    main()
