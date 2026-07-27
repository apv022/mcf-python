# Assets and archives

ZIP entries are validated before extraction: canonical paths, duplicates,
encryption, special types, counts, expanded sizes, totals, and compression
ratios are bounded. Failed temporary roots are deleted; successful parsed roots
remain until process exit because compilation may still need their bytes.
Tree output copies bytes; standalone output embeds local media and fonts with
MIME-correct data URLs.
