# Calculus I reference course

This course is authored as portable MCF 1.0 source. It is intended as both a real learning resource and a conformance stress test.

## Coverage

- 6 chapters and 18 lessons
- notes, practice, and assessment activities
- all core question types
- essay completion requirements
- Markdown tables, block quotes, and code fences
- inline and display LaTeX
- local SVG images
- external YouTube provider reference

The external video in the limits chapter requires internet access. All other authored content and images are local.

The course declares `CC-BY-4.0` in `manifest.yaml`. Compile it from the repository root with:

```bash
npm run mcf -- validate examples/calculus-i
npm run mcf -- compile examples/calculus-i --output courses
```

It is also included in `npm run compile:examples`.
