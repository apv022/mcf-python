# Compilation pipeline

```text
CLI/API → package_reader → manifest/version → version parser/schema
→ semantic/package-set resolution → dataclasses → render
→ atomic tree or one-file output → shared browser runtime
```

`compile_course` copies bytes and packaged reader/math assets into a staged
directory. `compile_single_file` MIME-encodes local media/fonts and embeds data,
CSS, and the same runtime into one atomically replaced HTML file.
