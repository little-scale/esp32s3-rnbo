# Initial port draft, without qualification

The initial generator/reference/catalog and three graphs are frozen here. The
scale exponent and mtof/ftom tuning ports were subsequently wired explicitly,
after checking primary Gen constructor definitions. These corrections preceded
native and hardware execution; all 42 intended output streams and limits remain
unchanged. Other graph paths resolve one directory up via source-locations.json.

The exact initial adapter is draft_lowerer.mjs; its hash matches the original
export metadata. It is not an admitted qualified-lowerer snapshot. Do not run
the archived generator in place: its root calculation uses the original depth.
