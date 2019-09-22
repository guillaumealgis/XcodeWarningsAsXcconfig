# Xcode Warnings to .xcconfig

[![MIT](https://img.shields.io/github/license/guillaumealgis/XcodeWarningsAsXcconfig.svg)](https://tldrlegal.com/license/mit-license)
[![Build Status](https://img.shields.io/travis/guillaumealgis/XcodeWarningsAsXcconfig/master.svg)](https://travis-ci.org/guillaumealgis/XcodeWarningsAsXcconfig)

warnings2xcconfig is a tool to extract compiler and static analyzer warning flags from Xcode and format them into [a xcconfig file you can use in your projects](http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/).

It provides sensible defaults for each flag so you can get as much help from the compiler as possible.

## Ready-to-use xcconfig files

You can find pre-generated xcconfig files for your version of Xcode in the `Xcode-*` folders. Each folder contains a few xcconfig files with differents default settings (one per `--defaults` option, see below for what each option means).

## Usage

To produce a xcconfig file with strict, hand-picked defaults, run:

```bash
python warnings2xcconfig.py --defaults strict > Warnings.xcconfig
```

This will produce a xcconfig file with **strict, but pragmatic, handpicked default values** for each build setting.


### Available styles

The possible values you can pass to the `--defaults` flag are:

#### Strict

Use strict, hand-picked default values. Those are similar to "agressive", but with some warnings turned off to keep day-to-day development sane:

```bash
python warnings2xcconfig.py --defaults strict
```

#### Clang

Use Clang's default values:

```bash
python warnings2xcconfig.py --defaults clang
```

#### Xcode

Use Xcode's default values (the ones you get when creating a new project):

```bash
python warnings2xcconfig.py --defaults xcode
```

#### Aggressive

Enable all warnings, using the most aggressive option available for each flag:

```bash
python warnings2xcconfig.py --defaults aggressive
```

#### None

If you pass `none`, or do not include the `--defaults` flag at all, the xcconfig file will be generated without default values, but with comments listing the valid values for each flag.

For example:

```bash
$ python warnings2xcconfig.py --defaults none
// Generated using XcodeWarningsAsXcconfig
// https://github.com/guillaume-algis/XcodeWarningsAsXcconfig

// Apple LLVM 7.1 - Warnings - Objective C and ARC
CLANG_WARN_OBJC_REPEATED_USE_OF_WEAK = // YES | NO
CLANG_WARN_OBJC_EXPLICIT_OWNERSHIP_TYPE = // YES | NO

... snip ...

// Static Analyzer - Analysis Policy
RUN_CLANG_STATIC_ANALYZER = // YES | NO
CLANG_STATIC_ANALYZER_MODE = // shallow | deep
CLANG_STATIC_ANALYZER_MODE_ON_ANALYZE_ACTION = // shallow | deep
```

You can then pick the settings you want to enable or not for your specific needs.

### Clang Static Analyzer

If you decide to include Clang Static Analyzer flags in your xcconfig (which is the default), remember to enable the Static Analyzer in your project.

It can be done with the following flags (either in your xcconfig or Xcode project):

```bash
RUN_CLANG_STATIC_ANALYZER // YES | NO
CLANG_STATIC_ANALYZER_MODE // deep | shallow
CLANG_STATIC_ANALYZER_MODE_ON_ANALYZE_ACTION // deep | shallow
```

### Custom Xcode install

By default, the script will use `xcode-select -p` to find your Xcode installation path. If you want to extract warnings from another Xcode install (say, a Beta), use the `--xcode-path` flag:

```bash
python warnings2xcconfig.py --xcode-path /Applications/Xcode-Beta.app/
```

## Diff

To find out what changed between two version of Xcode, you can use the following command (in bash):

```bash
diff <(grep -E "^[^/ ]" Xcode-7.3/Warnings-XcodeDefaults.xcconfig | sort) <(grep -E "^[^/ ]" Xcode-10.0/Warnings-XcodeDefaults.xcconfig | sort)
```

*(replace the xcconfig files to compare in the command)*

## Contributing

All PRs are welcome, just try to respect PEP-8, and make sure the code is formatted using [Black](https://github.com/psf/black).

The hand-picked values for the `--defaults strict` flag are really open to change (see the first few line of the script), I'd be super happy to get feedback on real-world results of using these.

## Credits

This project is largely inpired from other great xcconfig projects and blog posts:

- [https://github.com/jonreid/XcodeWarnings](https://github.com/jonreid/XcodeWarnings)
- [https://github.com/tewha/MoreWarnings-xcconfig](https://github.com/tewha/MoreWarnings-xcconfig)
- [http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/](http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/)

Credit to [@steipete](https://twitter.com/steipete) for finding the [Clang Analyzer alpha checkers](https://gist.github.com/steipete/86c4db2cda22aa7427bb453907885c1f).

## Author

Guillaume Algis ([@guillaumealgis](https://twitter.com/guillaumealgis))
