# Xcode Warnings to .xcconfig

warnings2xcconfig is a tool to extract compiler and static analyzer warning flags from Xcode and format them into [a xcconfig file you can use in your projects](http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/).

It provides sensible defaults for each flag so you can get as much help from the compiler as possible.

## Ready-to-use xcconfig files

You can find pre-generated xcconfig files for your version of Xcode in the `Xcode-*` folders. Each folder contains a few xcconfig files with differents default settings (one per `--defaults` option, see "Usage" for what each option means).

## Usage

To produce a xcconfig file with strict, hand-picked defaults, use:

```bash
python warnings2xcconfig.py --defaults strict > Warnings.xcconfig
```


### Other `--defaults` options

Use LLVM-Clang's default values:

```bash
python warnings2xcconfig.py --defaults clang
```

Use default values Xcode picks when creating a new project:

```bash
python warnings2xcconfig.py --defaults xcode
```

Enable all warnings, using the most aggressive option available for each flag:

```bash
python warnings2xcconfig.py --defaults aggressive
```

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

// Static Analyzer - Analysis Policiy
RUN_CLANG_STATIC_ANALYZER = // YES | NO
CLANG_STATIC_ANALYZER_MODE = // shallow | deep
CLANG_STATIC_ANALYZER_MODE_ON_ANALYZE_ACTION = // shallow | deep
```

### Custom Xcode install

By default, the script will use `xcode-select -p` to find your Xcode installation path. If you want to extract warnings from another Xcode install (say, a Beta), use the `--xcode-path` flag:

```bash
python warnings2xcconfig.py --xcode-path /Applications/Xcode-Beta.app/
```


## Contributing

All PRs are welcome, just try to stick to the 80 cols rule and respect PEP-8.

The hand-picked values for the `--defaults strict` flag are really open to change (see the first few line of the script), I'd be super happy to get feedback on real-world results of using these.

## Credits

This project is largely inpired from other great xcconfig projects and blog posts:

- [https://github.com/jonreid/XcodeWarnings](https://github.com/jonreid/XcodeWarnings)
- [https://github.com/tewha/MoreWarnings-xcconfig](https://github.com/tewha/MoreWarnings-xcconfig)
- [http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/](http://www.jontolof.com/cocoa/using-xcconfig-files-for-you-xcode-project/)

## Author

Guillaume Algis ([@guillaumealgis](https://twitter.com/guillaumealgis))
